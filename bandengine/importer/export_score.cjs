// alphaTab supplies the expanded performance order, including repeat endings.
const fs = require('node:fs');
const at = require('@coderline/alphatab');
const {describeTrack,drumNote}=require('./instrument_catalog.cjs');
function loadPerformance(file, requested = -1) {
  const settings = new at.Settings();
  settings.core.logLevel = at.LogLevel.None;
  at.Logger.logLevel = at.LogLevel.None;
  const score = at.importer.ScoreLoader.loadScoreFromBytes(new Uint8Array(fs.readFileSync(file)), settings);
  const tracks = score.tracks.map(describeTrack).filter(t=>t.supported);
  if (!tracks.length) throw Error('This score has no playable guitar, four-string bass or drum-kit track.');
  const chosen = requested < 0 ? (tracks.find(t => /lead/i.test(t.name)) || tracks.find(t => t.program >= 24 && t.program <= 31) || tracks[0]) : tracks.find(t => t.index === requested);
  if (!chosen) throw Error(`Track ${requested} is not a supported playable instrument.`);
  const track = score.tracks[chosen.index];
  const staff = track.staves.find(s => chosen.family==='drums'?s.isPercussion:!s.isPercussion&&s.tuning.length===chosen.strings);
  const midi = new at.midi.MidiFile();
  const generator = new at.midi.MidiFileGenerator(score, settings, new at.midi.AlphaSynthMidiFileHandler(midi, false));
  generator.generate();
  const masterBars = generator.tickLookup.masterBars;
  const changes = masterBars.flatMap(m => m.tempoChanges.map(c => ({tick:c.tick, tempo:c.tempo}))).sort((a,b)=>a.tick-b.tick);
  if (!changes.length || changes[0].tick > 0) changes.unshift({tick:0, tempo:score.tempo || 120});
  let last = 0, elapsed = 0, tempo = score.tempo || 120;
  const segments=[];
  for(const c of changes) {elapsed += (c.tick-last)/960*60/tempo; segments.push({...c,time:elapsed}); last=c.tick; tempo=c.tempo;}
  function seconds(tick) {
    let lo=0, hi=segments.length;
    while(lo+1<hi){const mid=(lo+hi)>>1; if(segments[mid].tick<=tick)lo=mid;else hi=mid;}
    const s=segments[lo];return s.time+(tick-s.tick)/960*60/s.tempo;
  }
  return {score, track, staff, chosen, tracks, masterBars, seconds};
}
function exportScore(file, requested = -1) {
  const {score,track,staff,chosen,tracks,masterBars,seconds}=loadPerformance(file, requested);
  const events=[], bars=[], active=new Map(), warnings=new Set();
  for (const mb of masterBars) {
    bars.push({bar:mb.masterBar.index+1,start:seconds(mb.start),end:seconds(mb.end),tempo:mb.tempoChanges[0]?.tempo || score.tempo});
    const seen=new Set();
    for(let slice=mb.firstBeat;slice;slice=slice.nextBeat) for(const item of slice.highlightedBeats){
      const b=item.beat;
      if(b.voice.bar.staff !== staff || seen.has(b.id))continue;
      seen.add(b.id);
      const tick=mb.start+item.playbackStart;
      for(const n of b.notes){
        const start=seconds(tick), end=seconds(tick+b.playbackDuration);
        if(staff.isPercussion){
          const drum=drumNote(n,track);
          if(!drum.piece){warnings.add(`Percussion MIDI ${drum.midi} is outside this acoustic kit and is omitted.`);continue;}
          events.push({start,duration:Math.max(.015,end-start),string:0,fret:0,midi:drum.midi,target:null,
            articulation:'hit',velocity:Math.min(124,Math.max(12,32+Number(b.dynamics)*12+(n.accentuated?10:0)-(n.isGhost?24:0))),
            vibrato:0,bend:[],finger:0,position:0,bar:mb.masterBar.index+1,pick:false,piece:drum.piece,openAmount:drum.openAmount});continue;
        }
        if(n.string < 1 || n.string > chosen.strings || n.fret < 0)continue;
        const string=n.string-1;
        if(n.isTieDestination && active.has(string)) {const prior=active.get(string); prior.duration=Math.max(prior.duration,end-prior.start);continue;}
        let articulation='pick', target=null;
        const midi=staff.tuning[chosen.strings-n.string]+staff.capo+n.fret;
        const bends=(n.bendPoints || []).map(p=>({offset:p.offset/60,value:p.value/2}));
        if(n.isDead)articulation='dead_note';
        else if(bends.length){const first=bends[0].value, peak=Math.max(...bends.map(p=>p.value)), final=bends.at(-1).value;
          articulation=first>0 && final<first ? 'prebend_release' : final<peak ? 'bend_release' : 'bend_up'; target=midi+peak;
        }else if(n.slideTarget && n.slideOutType){articulation='legato_slide';target=staff.tuning[chosen.strings-n.string]+staff.capo+n.slideTarget.fret;}
        else if(n.isHammerPullDestination){articulation=n.hammerPullOrigin && n.fret < n.hammerPullOrigin.fret ? 'pull_off':'hammer_on';}
        else if(n.isPalmMute)articulation='palm_mute';
        else if(n.harmonicType){articulation='pinch_harmonic';warnings.add('Harmonics use the physical engine harmonic approximation.');}
        else if(n.accentuated)articulation='accent';
        if(b.tremoloPicking || n.trillValue>=0)warnings.add('Trills and tremolo picking are represented by their written beat, without ornament subdivision.');
        const e={start,duration:Math.max(.015,end-start),string,fret:n.fret,midi,target,articulation,
          velocity:Math.min(124,Math.max(35,32+Number(b.dynamics)*12+(n.accentuated?10:0))),vibrato:n.vibrato?18:0,bend:bends,
          finger:Number(n.leftHandFinger),bar:mb.masterBar.index+1,pick:!n.isHammerPullDestination && !n.isTieDestination};
        events.push(e); active.set(string,e);
      }
    }
  }
  events.sort((a,b)=>a.start-b.start||a.string-b.string);
  if(staff.isPercussion){
    let time=-1,used=new Set(),alternate=0;
    for(const e of events){
      if(e.start!==time){time=e.start;used.clear();}
      if(e.piece==='kick'){e.limb=2;continue;}
      if(e.midi===44){e.limb=3;continue;}
      let hand=e.piece==='snare'?0:['hihat','ride'].includes(e.piece)?1:alternate++%2;
      if(used.has(hand))hand=1-hand;
      if(used.has(hand))warnings.add('More than two simultaneous stick hits: the visible hand motion is approximated.');
      e.limb=hand;used.add(hand);
    }
  }
  if(!events.length)throw Error('The selected track has no playable notes.');
  return {version:1,title:score.title||require('node:path').basename(file),artist:score.artist||'',source:file,track:chosen.index,trackName:chosen.name,
    tracks,family:chosen.family,tone:chosen.tone,program:chosen.program,strings:chosen.strings,
    baseTuning:staff.isPercussion?[]:[...staff.tuning].reverse(),
    tuning:staff.isPercussion?[]:[...staff.tuning].reverse().map(n=>n+staff.capo),capo:staff.isPercussion?0:staff.capo,tempo:score.tempo,events,bars,
    duration:seconds(masterBars.at(-1).end),warnings:[...warnings]};
}
module.exports={exportScore,loadPerformance};
if(require.main===module){try{process.stdout.write(JSON.stringify(exportScore(process.argv[2],Number(process.argv[3]??-1))));}catch(e){console.error(e.stack);process.exit(1);}}

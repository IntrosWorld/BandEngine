// One instrument contract for the chooser, audio renderer and native views.
const GUITARS=['Nylon acoustic guitar','Steel acoustic guitar','Jazz electric guitar','Clean electric guitar',
  'Muted electric guitar','Overdriven guitar','Distortion guitar','Guitar harmonics'];
const DRUMS={35:'kick',36:'kick',37:'snare',38:'snare',39:'snare',40:'snare',
  41:'tom_floor',43:'tom_floor',45:'tom_low',47:'tom_mid',48:'tom_high',50:'tom_high',
  42:'hihat',44:'hihat',46:'hihat',49:'crash',52:'crash',55:'crash',57:'crash',
  51:'ride',53:'ride',59:'ride',91:'snare',92:'hihat',93:'ride'};
function drumNote(note,track){
  const index=note.percussionArticulation;
  const midi=track.percussionArticulations[index]?.outputMidiNumber??index;
  return {midi,piece:DRUMS[midi],openAmount:midi===46?1:midi===44?.05:0};
}
function describeTrack(t){
  const staff=t.staves.find(s=>s.isPercussion)||t.staves.find(s=>[4,6].includes(s.tuning.length));
  const strings=staff?.tuning.length||Math.max(0,...t.staves.map(s=>s.tuning.length));
  const program=t.playbackInfo.program,percussion=Boolean(staff?.isPercussion);
  const family=percussion?'drums':strings===4?'bass':[24,25].includes(program)?'acoustic':'electric';
  const tone=family==='electric'?([29,30].includes(program)?'distortion':'clean'):family;
  const notes=staff?.bars.flatMap(b=>b.voices.flatMap(v=>v.beats.flatMap(b=>b.notes)))||[];
  const playable=percussion?notes.some(n=>drumNote(n,t).piece):notes.some(n=>n.fret>=0&&n.string>=1&&n.string<=strings);
  const capo=percussion?0:(staff?.capo||0);
  const invalidCapo=!Number.isInteger(capo)||capo<0||capo>24;
  const tooHigh=!percussion&&notes.some(n=>n.fret+capo>24 || (n.slideTarget&&n.slideTarget.fret+capo>24));
  const supported=Boolean(staff&&playable&&!tooHigh&&!invalidCapo);
  const instrument=percussion?'Drums / percussion':GUITARS[program-24]||(family==='bass'?'Bass':`MIDI instrument ${program+1}`);
  const reason=supported?'':!staff?`${strings||'No'} strings - requires six-string guitar or four-string bass`:
    invalidCapo?'Capo must be a whole fret from 0 to 24':tooHigh?(capo?`Capo ${capo} places a note beyond physical fret 24`:'Frets above 24 are outside the instrument range'):percussion?'No supported drum-kit hits':'No playable guitar notes';
  return {index:t.index,name:t.name||`Track ${t.index+1}`,instrument,strings,program,family,tone,capo,supported,reason,
    volume:t.playbackInfo.volume/16,pan:(t.playbackInfo.balance-8)/8,muted:t.playbackInfo.isMute,solo:t.playbackInfo.isSolo};
}
module.exports={describeTrack,drumNote};

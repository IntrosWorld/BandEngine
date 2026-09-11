const fs=require('node:fs');
const path=require('node:path');
const at=require('@coderline/alphatab');
const {describeTrack}=require('./instrument_catalog.cjs');
const {loadPerformance}=require('./export_score.cjs');

function listTracks(file) {
  const settings=new at.Settings();settings.core.logLevel=at.LogLevel.None;at.Logger.logLevel=at.LogLevel.None;
  const score=at.importer.ScoreLoader.loadScoreFromBytes(new Uint8Array(fs.readFileSync(file)),settings);
  const tracks=score.tracks.map(describeTrack);
  let duration=0;
  if(tracks.some(t=>t.supported)) {
    const performance=loadPerformance(file);
    duration=performance.masterBars.length?performance.seconds(performance.masterBars.at(-1).end):0;
  }
  return {title:score.title||path.basename(file),source:path.resolve(file),duration,tracks};
}
module.exports={listTracks};
if(require.main===module){try{process.stdout.write(JSON.stringify(listTracks(process.argv[2])));}catch(e){console.error(e.message);process.exitCode=1;}}

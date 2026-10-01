// Rasterize vector guidance only. This is never used to upscale rendered media.
const fs = require('node:fs');
const sharp = require('sharp');
const [source, destination] = process.argv.slice(2);
sharp(fs.readFileSync(source), {density: 300}).resize({width: 2400}).flatten({background:'#fff'}).png().toFile(destination).catch(error=>{console.error(error.message);process.exitCode=1});

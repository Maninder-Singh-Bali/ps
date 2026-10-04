'use strict';
function parseCoordinates(value){
 const text=String(value).trim().replace(/[()]/g,'');if(!text)return {latitude:null,longitude:null};
 const parts=text.split(/\s*[,;]\s*/);if(parts.length!==2)throw Error('Paste latitude, longitude — for example 28.6139, 77.2090.');
 function coordinate(s,limit,axis){
  const m=s.trim().match(/^([+-]?\d+(?:\.\d+)?)\s*°?\s*(?:([0-9]+(?:\.\d+)?)\s*[′']\s*(?:([0-9]+(?:\.\d+)?)\s*[″"]\s*)?)?([NSEW])?$/i);
  if(!m)throw Error('Use decimal coordinates or degrees, minutes and seconds.');
  const hemisphere=m[4]?.toUpperCase();if(hemisphere&&!(axis==='latitude'?'NS':'EW').includes(hemisphere))throw Error('Latitude comes first (N/S), then longitude (E/W).');
  if(Number(m[2]||0)>=60||Number(m[3]||0)>=60)throw Error('Minutes and seconds must be below 60.');
  let v=Math.abs(Number(m[1]))+Number(m[2]||0)/60+Number(m[3]||0)/3600;
  const negative=hemisphere?'SW'.includes(hemisphere):m[1].startsWith('-');if(negative)v=-v;
  if(!Number.isFinite(v)||Math.abs(v)>limit)throw Error(`${axis} must be between −${limit} and ${limit}.`);return v;
 }
 return {latitude:coordinate(parts[0],90,'latitude'),longitude:coordinate(parts[1],180,'longitude')};
}
if(typeof module!=='undefined')module.exports={parseCoordinates};

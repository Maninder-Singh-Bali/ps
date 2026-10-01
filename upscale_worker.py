"""Isolated, tiled Real-ESRGAN inference; invoked with the installed Torch runtime."""
import argparse
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps
import torch
from spandrel import ModelLoader


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('source');parser.add_argument('target');parser.add_argument('weights')
    args=parser.parse_args()
    with Image.open(args.source) as source:
        im=ImageOps.exif_transpose(source).convert('RGB')
    if max(im.size)>1600 or im.width*im.height>2_000_000:
        raise ValueError('Use the native image for plans above the low-resolution limit.')
    device='cuda' if torch.cuda.is_available() else 'cpu'
    torch.set_num_threads(4)
    state=torch.load(args.weights,map_location='cpu',weights_only=True)
    model=ModelLoader().load_from_state_dict(state).eval().to(device)
    scale=model.scale
    if scale!=4:raise ValueError('Expected the installed 4x model.')
    pixels=np.asarray(im,dtype=np.float32)/255
    result=Image.new('RGB',(im.width*scale,im.height*scale))
    tile=192;pad=24
    with torch.inference_mode():
        for y in range(0,im.height,tile):
            for x in range(0,im.width,tile):
                right=min(x+tile,im.width);bottom=min(y+tile,im.height)
                left=max(0,x-pad);top=max(0,y-pad)
                crop=pixels[top:min(bottom+pad,im.height),left:min(right+pad,im.width)]
                tensor=torch.from_numpy(crop.copy()).permute(2,0,1).unsqueeze(0).to(device)
                output=model(tensor).squeeze(0).clamp(0,1).permute(1,2,0).cpu().numpy()
                patch=Image.fromarray((output*255).round().astype('uint8'))
                patch=patch.crop(((x-left)*scale,(y-top)*scale,(right-left)*scale,(bottom-top)*scale))
                result.paste(patch,(x*scale,y*scale))
    target=Path(args.target);temp=target.with_suffix('.partial.png')
    result.save(temp);temp.replace(target)


if __name__=='__main__':main()

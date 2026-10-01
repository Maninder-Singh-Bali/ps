"""Non-destructive raster preparation, with explicit source-coordinate provenance."""
import hashlib
from PIL import Image,ImageOps

def prepare(source,destination):
    with Image.open(source) as im:
        im.load();source_format=im.format;w,h=im.size;orientation=int(im.getexif().get(274,1));normalized=ImageOps.exif_transpose(im).convert('RGB')
        normalized.save(destination)
    transforms={1:[1,0,0,1,0,0],2:[-1,0,0,1,w,0],3:[-1,0,0,-1,w,h],4:[1,0,0,-1,0,h],
                5:[0,1,1,0,0,0],6:[0,1,-1,0,h,0],7:[0,-1,-1,0,h,w],8:[0,-1,1,0,0,w]}
    gray=normalized.convert('L');small=gray.copy();small.thumbnail((1200,1200))
    ink=small.point(lambda v:255 if v<180 else 0);box=ink.getbbox()
    content=[box[0]/small.width,box[1]/small.height,(box[2]-box[0])/small.width,(box[3]-box[1])/small.height] if box else None
    return {'format':source_format,'vector':False,'source_size':[w,h],'prepared_size':list(normalized.size),
            'source_file_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'source_to_prepared':transforms.get(orientation,transforms[1]),
            'orientation':orientation,'content_bounds':content,'cropped':False,'deskew_applied':False,
            'resolution_status':'low' if max(normalized.size)<=1600 else 'native',
            'line_quality':'requires visual verification','title_block_status':'unclassified; source evidence retained',
            'warnings':['Scale unknown. Use a known distance to calibrate.','Margins and annotations are retained. Deskew requires reliable line evidence.']}

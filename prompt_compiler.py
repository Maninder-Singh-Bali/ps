"""Conservative edit-prompt preparation from user words and explicit scene data.

No vision inference or language-model service is claimed. FLUX interprets the
request; this compiler adds the known target, references and preservation scope.
"""
import re

CORRECTIONS={'refrence':'reference','referance':'reference','refrences':'references','detials':'details','deatils':'details','consistancy':'consistency','geometery':'geometry','ligthing':'lighting','enviroment':'environment','backgroud':'background','chandller':'chandelier','kitechen':'kitchen','qaulity':'quality','teh':'the','dont':'do not','pls':'please'}


def prepare_edit(text,room,mode,products=()):
    raw=str(text or '').strip()
    if len(raw)>2500:raise ValueError('Keep the change description within 2,500 characters.')
    normalized=re.sub(r'\b[a-z]+\b',lambda m:CORRECTIONS.get(m[0].lower(),m[0]),raw,flags=re.I)
    normalized=re.sub(r'[\t ]+',' ',normalized)
    parts=[f"Edit the master photograph of {room}. Requested change: {normalized or 'Keep the existing scene consistent.'}"]
    if mode=='region':
        parts.append('The selected rectangle identifies the edit area. Words such as “this” or “here” refer to the subject in that area. Make the requested change only there. If replacing an object, remove the old target completely rather than mixing its design with the replacement. Preserve everything the request does not ask to change.')
    elif mode=='structure':
        parts.append('Keep the same camera viewpoint and room structure. Change only the features explicitly requested. Preserve all other furniture, openings and background connections.')
    else:
        parts.append('Use the master as a reference. Follow the requested changes and retain the other design details wherever possible.')
    if products:
        named='; '.join(f'{i+1}: {str(name)[:120]}' for i,name in enumerate(products))
        parts.append('Available furniture references: '+named+'. If the request mentions a reference, use that product’s design, not its photographed background. Do not add unrelated reference objects.')
    parts.append('Preserve explicit exclusions, object counts, materials and directions in the user’s request. Do not invent dimensions, extra objects or a new camera angle. Match the existing photographic detail, scale, contact shadows and reflections.')
    return {'original':raw,'normalized':normalized,'prompt':'\n\n'.join(parts),
            'method':'Local wording and scene-context preparation; FLUX interprets the requested edit.', 'version':1}

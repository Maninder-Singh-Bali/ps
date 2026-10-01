import test_studio
from pathlib import Path
import io, json
import unittest
from PIL import Image
import project_storage


class StorageTests(unittest.TestCase):
    setUp = test_studio.StudioTests.setUp
    tearDown = test_studio.StudioTests.tearDown
    call = test_studio.StudioTests.call
    asset = test_studio.StudioTests.asset


def test_custom_location_and_room_folders(self):
    parent=self.root/'User Projects'
    project=self.call('/api/projects',{'name':'Villa / north','save_parent':str(parent)})
    root=Path(project['storage_path'])
    self.assertTrue(root.is_relative_to(parent));self.assertTrue((root/'project.json').exists())
    room=self.call(f"/api/projects/{project['id']}/rooms",{'name':'Living Room','floor':'Lower'})
    image=io.BytesIO();Image.new('RGB',(40,30)).save(image,format='PNG')
    for kind,folder in [('plan','Floor_Plans'),('anchor','Room_References'),('reference','Furniture_References')]:
        response=self.client.post(self.url+f"/api/projects/{project['id']}/upload?kind={kind}&room_id={room['id']}",data=image.getvalue(),headers={'Content-Type':'application/octet-stream','X-Filename':'chair.png'})
        self.assertEqual(response.status_code,200,response.text)
        asset=self.st.asset(response.json()['assets'][0]['id']);path=Path(asset['path'])
        self.assertTrue(path.is_relative_to(root));self.assertIn(folder,path.parts)
    job={'project_id':project['id'],'id':'test-output','kind':'video','room_id':room['id']}
    output=project_storage.output_folder(self.st,job,root)
    self.assertIn('Videos',output.parts)
    original=project_storage.room_path(self.st,project['id'],room['id'])
    self.call(f"/api/projects/{project['id']}/rooms/{room['id']}",{'name':'Renamed room'},'PATCH')
    self.assertEqual(original,project_storage.room_path(self.st,project['id'],room['id']))
    manifest=json.loads((root/'project.json').read_text())
    self.assertTrue(all(not Path(a['path']).is_absolute() for a in manifest['assets'].values()))


def test_relocation_preserves_media_and_supporting_files(self):
    a=self.asset();self.st.room(self.pid,self.rid)['images'].append(a['id']);self.st.save()
    old_asset=Path(a['path']);original_bytes=old_asset.read_bytes();oldroot=project_storage.project_root(self.st,self.pid)
    (oldroot/'notes.txt').write_text('keep me')
    result=self.call(f'/api/projects/{self.pid}/storage',{'parent':str(self.root/'Moved projects')})
    newroot=Path(result['path']);current=self.st.asset(a['id'])
    self.assertTrue(Path(current['path']).is_relative_to(newroot));self.assertEqual(Path(current['path']).read_bytes(),original_bytes)
    self.assertEqual(old_asset.read_bytes(),original_bytes)
    self.assertEqual((newroot/'Supporting_Files'/'Previous_Location'/'notes.txt').read_text(),'keep me')
    self.assertEqual(self.client.get(self.url+'/media/'+a['id']).content,original_bytes)
    self.assertEqual(result['operation']['progress'],100)
    self.assertEqual(self.st.room(self.pid,self.rid)['images'],[a['id']])


def test_missing_file_and_active_jobs_keep_original_location(self):
    a=self.asset();oldroot=project_storage.project_root(self.st,self.pid)
    self.st.asset(a['id'])['path']=str(self.root/'missing.png')
    self.call(f'/api/projects/{self.pid}/storage',{'parent':str(self.root/'destination')},status=400)
    self.assertEqual(project_storage.project_root(self.st,self.pid),oldroot)
    self.assertEqual(self.st.storage_operations[self.pid]['status'],'failed')
    self.assertNotIn(self.pid,self.st.moving_projects)
    self.st.new_job(self.pid,'reference',self.rid,reference_prompt='test')
    self.call(f'/api/projects/{self.pid}/storage',{'parent':str(self.root/'destination')},status=400)
    self.assertEqual(project_storage.project_root(self.st,self.pid),oldroot)


def test_paths_cannot_overwrite_or_nest_existing_project(self):
    oldroot=project_storage.project_root(self.st,self.pid)
    self.call('/api/projects',{'name':'Bad','save_parent':'relative/path'},status=400)
    self.call(f'/api/projects/{self.pid}/storage',{'parent':str(oldroot/'nested')},status=400)
    occupied=self.root/'Not a folder';occupied.write_text('keep')
    self.call('/api/projects',{'name':'Bad','save_parent':str(occupied)},status=400)
    self.assertEqual(occupied.read_text(),'keep')


def test_legacy_job_history_remains_accessible_after_copy(self):
    p=self.st.project(self.pid);p.pop('storage_path');p.pop('storage_version')
    oldroot=project_storage.project_root(self.st,self.pid)
    job=self.st.new_job(self.pid,'image',self.rid,input_revision=1)
    job.update(status='completed')
    folder=oldroot/'jobs'/job['id'];folder.mkdir(parents=True)
    (folder/'history.json').write_text('{"completed":true}')
    self.st.save()
    result=self.call(f'/api/projects/{self.pid}/storage',{'parent':str(self.root/'Legacy copy')})
    current=self.st.db['jobs'][job['id']]
    self.assertTrue(Path(current['work_dir']).is_relative_to(Path(result['path'])))
    self.assertEqual((Path(current['work_dir'])/'history.json').read_text(),'{"completed":true}')
    self.assertTrue((folder/'history.json').exists())


for test in [test_custom_location_and_room_folders,test_relocation_preserves_media_and_supporting_files,test_missing_file_and_active_jobs_keep_original_location,test_paths_cannot_overwrite_or_nest_existing_project,test_legacy_job_history_remains_accessible_after_copy]:
    setattr(StorageTests,test.__name__,test)

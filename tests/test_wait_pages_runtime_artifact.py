"""Fail-closed Pages runtime visibility gate regression."""
import json
import subprocess
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class RuntimeArtifactGateTests(unittest.TestCase):
    def test_visibility_requires_same_id_and_two_consecutive_observations(self):
        script=r"""
const assert=require('node:assert/strict');
const {waitForRuntimeArtifact}=require('./scripts/wait_pages_runtime_artifact.cjs');
const expected={name:'github-pages',id:123};
const foreign={name:'verified-financial-1',id:456};
const response=(artifacts)=>({artifacts});
let calls=0;
const silent=()=>{};
const opts=(entries)=>({expectedId:'123',attempts:entries.length,sleep:async()=>{},log:silent,client:{
    listArtifacts:async()=>{calls++;const entry=entries.shift();if(entry instanceof Error)throw entry;return entry;}
}});
(async()=>{
    assert.equal(await waitForRuntimeArtifact(opts([response([foreign]),response([expected]),response([]),response([expected]),response([expected])])),true);
    assert.equal(calls,5);
    assert.equal(await waitForRuntimeArtifact(opts([new Error('transient'),response([expected]),response([expected])])),true);
    await assert.rejects(waitForRuntimeArtifact(opts([response([expected]),response([])])),/never became stably visible/);
    await assert.rejects(waitForRuntimeArtifact(opts([response([{name:'github-pages',id:999}])])),/differs/);
    await assert.rejects(waitForRuntimeArtifact(opts([response([expected,expected])])),/Multiple/);
    await assert.rejects(waitForRuntimeArtifact(opts([{}])),/Invalid runtime artifact list/);
    await assert.rejects(waitForRuntimeArtifact({...opts([response([expected])]),expectedId:''}),/Missing valid/);
    console.log('PAGES_RUNTIME_VISIBILITY_TESTS_OK');
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
        run=subprocess.run(['node','-e',script],cwd=ROOT,text=True,capture_output=True)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        self.assertIn('PAGES_RUNTIME_VISIBILITY_TESTS_OK',run.stdout)

    def test_both_workflows_use_uploaded_id_before_deployment(self):
        for filename in ('update.yml','stock-prices.yml'):
            workflow=(ROOT/'.github/workflows'/filename).read_text(encoding='utf-8')
            self.assertIn('id: pages_upload',workflow)
            self.assertIn('steps.pages_upload.outputs.artifact_id',workflow)
            self.assertIn('@actions/artifact@2.1.3',workflow)
            self.assertIn('new DefaultArtifactClient()',workflow)
            self.assertLess(workflow.index('actions/upload-pages-artifact@v3'),workflow.index('wait_pages_runtime_artifact.cjs'))
            self.assertLess(workflow.index('wait_pages_runtime_artifact.cjs'),workflow.index('actions/deploy-pages@v4'))
            self.assertNotIn('continue-on-error: true\n        id: deployment',workflow)

if __name__=='__main__':unittest.main()

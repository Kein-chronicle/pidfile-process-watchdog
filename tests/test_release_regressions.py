import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class RegressionTests(unittest.TestCase):
 def test_watchdog_corrupt_state_never_restarts(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);state=p/'state.json';state.write_text('broken');marker=p/'restarted'
   r=subprocess.run([sys.executable,str(ROOT/'scripts/watchdog.py'),'--pid-file',str(p/'missing'),'--root',d,'--state',str(state),'--restart-cmd','touch '+str(marker)],capture_output=True)
   self.assertNotEqual(r.returncode,0);self.assertFalse(marker.exists());self.assertEqual(state.read_text(),'broken')
if __name__=='__main__':unittest.main()

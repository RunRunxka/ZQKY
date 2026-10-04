"""Independent boundary probe: expired heartbeat cannot re-authorize late work."""
import atexit
import os
from pathlib import Path
import sys
import tempfile

_temporary=tempfile.TemporaryDirectory(prefix='zqky-v00-expired-heartbeat-')
atexit.register(_temporary.cleanup)
os.environ['ZQKY_DATA_DIR']=str(Path(_temporary.name)/'data')
os.environ['ZQKY_ENV']='test'
os.environ.pop('ZQKY_CREDENTIALS_FILE',None)
sys.path.insert(0,str(Path(__file__).resolve().parents[4]/'apps'/'api'))
from tests.test_question_lease_batches import LeaseFixture


def test_expired_heartbeat_cannot_reauthorize_organizer_intermediate_write(tmp_path):
    f=LeaseFixture(tmp_path); job=f.job(); lease=f.store.claim(job.job_id)
    f.clock.advance(31)
    assert not f.store.execution_allowed(lease)
    before=f.store.get(job.job_id)
    renewed=f.store.heartbeat(lease)
    after=f.store.get(job.job_id)
    current,created,_=f.catalog.record_organize_batch(job.job_id,batch_index=0,next_batch_index=1,
        draft_id=f.draft.draft_id,base_draft_revision=f.draft.revision,proposed_content=dict(f.draft.content),
        lease_attempt=lease.attempt,lease_token=lease.token,now=f.clock.now())
    print({'expiredHeartbeatAccepted':renewed,'expiredBatchCreatedAfterHeartbeat':created is not None,'checkpoint':current.checkpoint})
    assert renewed is False and after==before, 'An expired lease was revived by a late heartbeat'
    assert created is None

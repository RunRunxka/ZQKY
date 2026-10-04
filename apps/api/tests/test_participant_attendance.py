"""出勤校正：当前人次CAS/幂等/审计，不改身份历史或旧成绩。"""
from __future__ import annotations

import json

from app.core.sqlite import connect
from tests.scores_support import ScoresHarness, SAMPLE_HEADER, write_score_xlsx
from tests.test_scores_confirm import _confirm_body


def correct(harness, scene, body, participant_id=None):
    return harness.client.patch(
        f"/api/v1/assessments/{scene.assessment['assessmentId']}/participants/"
        f"{participant_id or scene.participants[0]['participantId']}/attendance", json=body,
    )


def test_attendance_cas_replay_conflict_and_audit(tmp_path):
    with ScoresHarness(tmp_path) as harness:
        scene = harness.create_scene(tag='attendance')
        before = dict(scene.participants[0])
        body = {'submissionId': 'attendance-1', 'expectedRevision': scene.assessment['revision'],
                'attendance': 'absent', 'reason': '教师按签到单确认缺考'}
        response = correct(harness, scene, body)
        assert response.status_code == 200, response.text
        result = response.json()
        assert result['assessment']['revision'] == scene.assessment['revision'] + 1
        assert result['participants'][0] == {**before, 'attendance': 'absent'}
        audit = result['attendanceCorrection']
        assert audit == {**audit, 'participantId': before['participantId'],
                         'previousAttendance': 'present', 'attendance': 'absent', 'reason': body['reason']}
        replay = correct(harness, scene, body)
        assert replay.status_code == 200 and replay.json()['replayed'] is True
        assert replay.json()['attendanceCorrection'] == audit
        conflict = correct(harness, scene, {**body, 'attendance': 'exempt'})
        assert conflict.status_code == 409 and conflict.json()['code'] == 'SUBMISSION_CONFLICT'
        stale = correct(harness, scene, {**body, 'submissionId': 'attendance-2'})
        assert stale.status_code == 409 and stale.json()['details']['currentRevision'] == result['assessment']['revision']
        conn = connect(harness.db_path)
        try:
            stored = conn.execute(
                "SELECT result_json FROM command_submissions WHERE operation='assessment.participant_attendance'"
            ).fetchall()
            assert len(stored) == 1
            assert json.loads(stored[0][0])['attendanceCorrection'] == audit
        finally:
            conn.close()


def test_attendance_rejects_cross_assessment_and_empty_reason(tmp_path):
    with ScoresHarness(tmp_path) as harness:
        first = harness.create_scene(tag='first')
        other = harness.create_scene(tag='other', students=(('乙', '0002'),))
        body = {'submissionId': 'bad', 'expectedRevision': first.assessment['revision'],
                'attendance': 'exempt', 'reason': '依据'}
        response = correct(harness, first, body, other.participants[0]['participantId'])
        assert response.status_code == 422
        assert 'participantId' in str(response.json()['details'])
        invalid = correct(harness, first, {**body, 'reason': '  '})
        assert invalid.status_code == 422
        assert harness.client.get(f"/api/v1/assessments/{first.assessment['assessmentId']}").json()['assessment']['revision'] == first.assessment['revision']


def test_attendance_does_not_mutate_confirmed_score_snapshot(tmp_path):
    with ScoresHarness(tmp_path) as harness:
        scene = harness.create_scene(tag='fixed')
        path = write_score_xlsx(tmp_path/'scores.xlsx', SAMPLE_HEADER, [['0001', '甲', 2, 3, 5]])
        upload = harness.upload_scores(scene.assessment['assessmentId'], path)
        assert upload.status_code == 201, upload.text
        confirmed = harness.confirm_import(upload.json()['importId'], _confirm_body(upload.json(), scene))
        assert confirmed.status_code == 200, confirmed.text
        revision_id = confirmed.json()['revisionId']
        before = harness.score_matrix(revision_id).json()
        body = {'submissionId': 'attendance-fixed', 'expectedRevision': confirmed.json()['assessmentRevision'],
                'attendance': 'absent', 'reason': '根据事后教师核对调整当前人次'}
        response = correct(harness, scene, body)
        assert response.status_code == 200, response.text
        assert harness.score_matrix(revision_id).json() == before
        assert before['revision']['participantSnapshot'][0]['attendance'] == 'present'

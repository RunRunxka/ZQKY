import copy
import pytest
from app.contracts import b4
from app.core.exceptions import AppError
from tests.practices_support import PracticesScene


@pytest.fixture
async def scene(tmp_path):
    value = await PracticesScene.create(tmp_path)
    yield value
    value.integrity()


async def test_ready_only_targets_replay_and_owner(scene):
    practice = scene.create_set()
    assert practice.current_revision.state=="draft" and practice.current_revision.items==[]
    original = scene.service.analysis.read_ready_report
    scene.service.analysis.read_ready_report=lambda *a,**kw: (_ for _ in ()).throw(AssertionError("replay preflight"))
    assert scene.create_set().replayed is True
    scene.service.analysis.read_ready_report=original
    with pytest.raises(AppError) as error:
        scene.create_set(submission="wrong-target",targets=("unknown",))
    assert error.value.status_code==422
    scene.service.owner_id="foreign"
    with pytest.raises(AppError) as error:
        scene.service.get_practice(practice.practice_set_id)
    assert error.value.status_code==404


async def test_whole_pool_greedy_coverage_dedup_gaps_unknown_explicit(scene):
    scene.question("只覆盖一",kps=("k1",))
    q = scene.question("双覆盖")
    duplicate=scene.question("双覆盖",answer=False)
    scene.question("未知难度",difficulty="unspecified")
    practice=scene.create_set(count=5)
    request=b4.PracticeSuggestionsRequest(expectedRevision=0,constraints={"count":5})
    result=scene.service.suggestions(practice.practice_set_id,request)
    assert result.selected_count==2 and result.items[0].question_id==min(q.question_id,duplicate.question_id)
    assert result.coverage["k1"]==2 and result.coverage["k2"]==1
    assert any("题量缺口：3" in x for x in result.gaps)
    unknown=scene.service.suggestions(practice.practice_set_id,request.model_copy(update={"constraints":b4.PracticeConstraints(count=5,includeUnknownDifficulty=True)}))
    assert unknown.selected_count==3
    unchanged=scene.service.get_practice(practice.practice_set_id)
    assert unchanged.revision==0 and unchanged.current_revision.constraints.count==5


async def test_exclude_original_by_surface_not_answer(scene):
    report=scene.analysis_scene.service.read_ready_report(scene.run_id)
    original=copy.deepcopy(report["originalQuestionContents"][0])
    original["type"]="short_answer"
    original["answer"]={"textMarkdown":"不同答案"}
    original["explanationMarkdown"]="不同解析"
    with scene.questions.write_transaction() as conn:
        scene.questions.insert_question_in(conn,owner_id="local",content=original,metadata={"subjectId":"math","difficulty":"easy"},answer_state="provided",
            content_fingerprint="fixture",source_spans=[],import_id=None,knowledge_links=[dict(knowledgePointId="k1",knowledgeRevisionId="k1-r",subjectIdSnapshot="math",knowledgeNameSnapshot="固定k1",role="primary")])
    practice=scene.create_set(targets=("k1",))
    result=scene.service.suggestions(practice.practice_set_id,b4.PracticeSuggestionsRequest(expectedRevision=0,constraints={"count":1}))
    assert result.selected_count==0 and len(result.gaps)==2


@pytest.mark.parametrize("question_type",["single_choice","multiple_choice","true_false","fill_blank","short_answer","other"])
async def test_unknown_original_type_matches_real_type_but_changed_surface_retained(scene,question_type):
    from app.services.practices.selection import original_surfaces
    from app.services.question_bank.fingerprint import duplicate_content_fingerprint
    original=copy.deepcopy(scene.analysis_scene.service.read_ready_report(scene.run_id)["originalQuestionContents"][0])
    original.pop("type",None)
    candidate=dict(original,type=question_type,answer={"textMarkdown":"不同答案"})
    assert duplicate_content_fingerprint(candidate) in original_surfaces([original])
    known=dict(original,type="short_answer")
    assert (duplicate_content_fingerprint(candidate) in original_surfaces([known]))==(question_type=="short_answer")
    changed=copy.deepcopy(candidate)
    changed["richContent"]["stemBlocks"][0]["text"]="不同实质题面"
    changed["stemMarkdown"]="不同实质题面"
    assert duplicate_content_fingerprint(changed) not in original_surfaces([original])


@pytest.mark.parametrize("mutation",["parent-cycle","parent-scored","missing-block","wrong-kp","score-sum","duplicate-node","empty-leaf"])
async def test_draft_explicit_tree_validation_zero_partial(scene,mutation):
    question=scene.question()
    practice=scene.create_set()
    item=scene.item(question)
    node=item["itemStructure"]["nodes"][0]
    if mutation=="parent-cycle": node["parentNodeKey"]="leaf"
    elif mutation=="parent-scored": item["itemStructure"]["nodes"].append(dict(node,nodeKey="child",parentNodeKey="leaf",ordinal=2,questionNo="child"))
    elif mutation=="missing-block": node["sourceBlockIds"]=["missing"]
    elif mutation=="wrong-kp": node["knowledgePointIds"]=["alien"]
    elif mutation=="score-sum": node["maxScore"]="1.26"
    elif mutation=="duplicate-node": item["itemStructure"]["nodes"].append(dict(node,ordinal=2,questionNo="child"))
    else: node["sourceBlockIds"]=[]
    with pytest.raises(AppError) as error: scene.save(practice,[item])
    assert error.value.status_code==422
    current=scene.service.get_practice(practice.practice_set_id)
    assert current.revision==0 and current.current_revision.items==[]


@pytest.mark.parametrize("score",["0","-1","1.001","1e2","NaN","999999999999999.00"])
async def test_decimal_text_rejects_unsafe_values(scene,score):
    practice=scene.create_set()
    with pytest.raises(AppError): scene.save(practice,[scene.item(scene.question(),score=score)])
    assert scene.service.get_practice(practice.practice_set_id).revision==0


async def test_source_paper_title_prefers_title_snapshot_and_null_when_missing(scene):
    """sourcePaperTitle/sourceCreatedAt 走“名称优先”：analysis_runs → paper_revisions.
    title_snapshot / created_at 只读派生（同 owner 校验）；来源缺失时落 null，不伪造名称。"""
    practice=scene.create_set()
    view=scene.service.get_practice(practice.practice_set_id)
    # 有值路径：种子报告的固定原卷标题快照「固定标题」与运行 created_at
    import sqlite3
    with scene.catalog.read_connection() as conn:
        row=conn.execute("SELECT created_at FROM analysis_runs WHERE id=?",(scene.run_id,)).fetchone()
    assert view.source_paper_title=="固定标题"
    assert view.source_created_at==row["created_at"]
    assert view.current_revision.source_paper_title=="固定标题"
    assert view.current_revision.source_created_at==view.source_created_at
    # 改 papers.title 不影响修订级快照（title_snapshot 只读派生自 paper_revisions）
    with scene.catalog.write_transaction() as conn:
        conn.execute("UPDATE papers SET title='后来卷名' WHERE id='paper'")
    assert scene.service.get_practice(practice.practice_set_id).source_paper_title=="固定标题"
    # 缺失为 null：来源运行不存在 / 非同 owner（异常与越权数据）时读路径落 null，不伪造名称
    from app.repositories.teaching.practices import PracticeRepository
    with scene.catalog.read_connection() as conn:
        assert PracticeRepository(scene.catalog).source_view_in(conn,"no-such-run","local")==(None,None)
        assert PracticeRepository(scene.catalog).source_view_in(conn,scene.run_id,"foreign")==(None,None)


async def test_fixed_old_question_new_current_and_cas(scene):
    q=scene.question("旧题面")
    practice=scene.save(scene.create_set(),[scene.item(q)])
    updated=scene.questions.patch_question(q.question_id,expected_revision=1,content=dict(q.content,stemMarkdown="新题面"),metadata=q.metadata,answer_state=q.answer_state,content_fingerprint="new")
    assert updated.current_revision_id!=q.current_revision_id
    reviewed=scene.review(practice)
    assert reviewed.current_revision.items[0].question_revision_id==q.current_revision_id
    assert reviewed.current_revision.items[0].content.stem_blocks[0].text=="旧题面"
    with pytest.raises(AppError) as error: scene.save(practice,[scene.item(q)])
    assert error.value.code=="REVISION_CONFLICT" and error.value.details["currentRevision"]==2


async def test_review_ref_archive_and_replay_before_activity(scene):
    q=scene.question()
    practice=scene.save(scene.create_set(),[scene.item(q)])
    reviewed=scene.review(practice)
    scene.questions.archive_question(q.question_id)
    assert scene.review(practice).replayed is True
    new=scene.service.new_revision(reviewed.practice_set_id,b4.PracticeRevisionRequest(submissionId="copy",sourceRevisionId=reviewed.current_revision.practice_revision_id))
    assert new.current_revision.items and new.current_revision.state=="draft"
    with pytest.raises(AppError): scene.review(new,submission="review-new")
    assert scene.service.get_revision(new.practice_set_id,reviewed.current_revision.practice_revision_id).model_dump()==reviewed.current_revision.model_dump()


async def test_gap_blocks_review_and_unknown_constraints(scene):
    q=scene.question(kps=("k1",))
    practice=scene.save(scene.create_set(count=2),[scene.item(q,kps=("k1",))])
    with pytest.raises(AppError) as error: scene.review(practice)
    assert error.value.code=="PRACTICE_COVERAGE_GAP"
    with pytest.raises(AppError): scene.service.suggestions(practice.practice_set_id,b4.PracticeSuggestionsRequest(expectedRevision=1,constraints={"count":1,"questionTypes":["invented"]}))


async def test_legacy_math_projected_and_unlocated_image_blocked(scene):
    q=scene.question(r"计算 $x^2$ 和 $$\frac{1}{2}$$")
    item=scene.item(q)
    practice=scene.save(scene.create_set(),[item])
    assert [x.kind for x in practice.current_revision.items[0].content.stem_blocks].count("formula")==2
    bad=scene.question("![图片](remote)")
    with pytest.raises(AppError) as error: scene.item(bad)
    assert error.value.code=="PRACTICE_RICH_REVIEW_REQUIRED"


async def test_candidates_beyond_default_page_read_complete_confirmed_pool(scene):
    for n in range(60):scene.question("候选"+str(n),kps=("k1",))
    q=scene.question("稀缺目标",kps=("k2",))
    assert len(scene.service.questions.list_confirmed(subject_id="math"))==61
    practice=scene.create_set(count=2)
    result=scene.service.suggestions(practice.practice_set_id,b4.PracticeSuggestionsRequest(expectedRevision=0,constraints={"count":2}))
    assert result.gaps==[] and q.current_revision_id in [x.question_revision_id for x in result.items]


async def test_complete_question_numbers_unique_across_selections(scene):
    q1=scene.question("甲题");q2=scene.question("乙题")
    practice=scene.create_set(count=2)
    first=scene.item(q1);second=scene.item(q2,ordinal=2)
    first["itemStructure"]["nodes"][0]["questionNo"]="16(1)"
    second["itemStructure"]["nodes"][0]["questionNo"]="16(1)"
    with pytest.raises(AppError) as error:scene.save(practice,[first,second])
    assert error.value.status_code==422 and error.value.details["issues"][0]["field"]=="questionNo"
    assert scene.service.get_practice(practice.practice_set_id).revision==0

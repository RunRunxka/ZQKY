"""B6 integration fixture. Import is inert; caller establishes isolation first.

Existing immutable seed code creates real four-catalog data and endpoint jobs.
Only provider HTTP transport is substituted. No TCP listener or product patch.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SEED = ROOT / 'docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-v00/v3/browser/seed_runtime.py'


def prior_seed_module():
    spec = importlib.util.spec_from_file_location('b6_integration_immutable_seed', SEED)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TEACHER = dict(title='B6教师标题《有理数加法》', totalLessons='3', currentLessonNo='2',
    lessonTypes=['review', 'other', 'review'], otherTypeText='B6教师指定课型',
    coreCompetencies='B6原素养：符号与依据。', keyPoints='B6原重点：保留原教师安排。',
    teachingDesign='B6原设计：先独立作答。',
    process=[dict(id='b6-teacher-a', stage='教师原环节', design='教师原设计', secondary='教师原二次备课')],
    exercises='B6原练习：保留原教师作业。', reflection='B6教师反思：五字段应用不能修改。')

FIVE = ['coreCompetencies', 'keyPoints', 'teachingDesign', 'process', 'exercises']
SIX = ['title', 'totalLessons', 'currentLessonNo', 'lessonTypes', 'otherTypeText', 'reflection']

# Handwritten oracle, not a production aggregate / merge / provider-output reader.
PATCH_TEXT = dict(coreCompetencies='候选素养：基于固定班级计数开展解释。',
    keyPoints='候选重点：有理数运算和复核。', teachingDesign='候选设计：独立判断、同伴比较与出口检测。',
    exercises='候选练习：使用固定正式题，说明运算依据。')
PROCESS_TEXT = [dict(stage=stage, design='候选活动'+str(n), secondary='候选二次'+str(n))
    for n, stage in enumerate(['情境导入', '合作探究', '独立练习', '归纳检测'], 1)]


def fixed_reply():
    return dict(patch={**PATCH_TEXT, 'process': [dict(id=f'new:N{n}', **item)
        for n, item in enumerate(PROCESS_TEXT, 1)]}, budget=dict(durationMinutes=43,
        stages=[dict(processId=f'new:N{n}', phase=phase, minutes=minute,
            knowledgeAliases=['K1'], activity='读题并解释固定依据', check='出口题与口头解释', evidenceAliases=['E1'])
            for n, (phase, minute) in enumerate(zip(['introduction', 'exploration', 'practice', 'conclusion'], [11, 11, 11, 10]), 1)]))

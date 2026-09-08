import type { LessonPlanData } from './types';
export const emptyData: LessonPlanData = {
  title: '',
  totalLessons: '1',
  currentLessonNo: '1',
  lessonTypes: ['new'],
  otherTypeText: '',
  coreCompetencies: '',
  keyPoints: '',
  teachingDesign: '',
  process: [],
  exercises: '',
  reflection: '',
};
export const exampleData: LessonPlanData = {
  title: '荷塘月色',
  totalLessons: '2',
  currentLessonNo: '1',
  lessonTypes: ['new'],
  otherTypeText: '',
  coreCompetencies:
    '1. 语言建构与运用：品味叠词、通感等语言表达，感受散文的音韵美。\n2. 思维发展与提升：梳理作者的游踪与情感变化，理解景与情的关系。\n3. 审美鉴赏与创造：体会月下荷塘的朦胧美，尝试用细腻的语言描绘生活中的景物。',
  keyPoints:
    '教学重点：赏析第4—6段写景语言，体会比喻、通感的表达效果。\n教学难点：理解作者“淡淡的喜悦”与“淡淡的哀愁”交织的情感。',
  teachingDesign:
    '以“循着月光，走进荷塘”为主线，采用诵读品味、情境教学与合作探究。\n板书设计：心中不宁 → 踱步荷塘 → 荷香月色 → 回归现实。',
  process: [
    {
      id: 'stage-1',
      stage: '情境导入 · 5分钟',
      design:
        '展示月下荷塘的画面，请学生用一个词描述感受。引出朱自清与《荷塘月色》，提出问题：作者为什么在这样的夜晚走出家门？',
      secondary: '关注学生的初读感受。',
    },
    {
      id: 'stage-2',
      stage: '初读感知 · 10分钟',
      design:
        '学生自由朗读课文，圈画表示游踪的词句。小组梳理行文线索，概括作者出门前、漫步时、回家后的心情变化。',
      secondary: '用游踪图辅助梳理。',
    },
    {
      id: 'stage-3',
      stage: '品读赏析 · 20分钟',
      design:
        '聚焦第4—6段。选择最喜欢的一句写景语句，从用词、修辞与感官三个角度分享理由。比较“清香”与“远处高楼上渺茫的歌声”，体会通感带来的阅读感受。',
      secondary: '引导学生联系语境分析。',
    },
    {
      id: 'stage-4',
      stage: '迁移小结 · 10分钟',
      design:
        '回到开篇“这几天心里颇不宁静”，交流景物与情感的联系。用80字描写校园中的一处景物，尝试运用一种本课所学的表达手法。',
      secondary: '允许不同理解，以文本为依据。',
    },
  ],
  exercises:
    '课堂练习：选择一处通感句，说明它沟通了哪些感官，有什么表达效果。\n课后作业：完成一段150字的写景片段，至少运用一种本课学到的手法。',
  reflection: '',
};
export const requirementExample =
  '课题：荷塘月色\n总课时：2\n本节课：1\n课型：新课\n核心素养：品味语言之美，理解景物描写与情感表达的关系。\n教学重点：赏析第4—6段中的通感与叠词。\n教学过程：\n情境导入 | 展示荷塘画面，引导学生交流初读感受。 | 关注学生体验\n诵读赏析 | 小组合作分析写景语句，交流修辞效果。 | 结合文本指导\n作业：写一段150字的校园景物描写。';

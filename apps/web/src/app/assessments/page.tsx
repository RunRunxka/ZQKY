import { redirect } from 'next/navigation';

/**
 * `施测与成绩` 模块入口（`/assessments`）：本模块分成两个单独页面
 * （班级管理 `/assessments/roster`、试卷管理 `/assessments/papers`，需求 6），
 * 模块根没有独立内容，直接重定向到班级管理页。
 */
export default function AssessmentsIndexPage() {
  redirect('/assessments/roster');
}

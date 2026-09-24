'use client';
import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Archive, ArrowLeft, ArrowRight, Layers, Loader2, Plus, Sparkles } from 'lucide-react';
import { Modal } from '@/components/ui/Modal';
import {
  COURSE_COLOR_DOT,
  COURSE_COLORS,
  CourseValidationError,
  createCourse,
  loadDemoCourses,
  readCourses,
  subscribeCourses,
  syllabusSummary,
  type CourseColor,
  type StudyCourse,
} from '@/services/courses-store';
import '@/features/space/styles/space.css';
import '@/features/courses/courses.css';

export function CoursesShelf() {
  const router = useRouter();
  const [courses, setCourses] = useState<StudyCourse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const refresh = useCallback(() => {
    try {
      setCourses(readCourses());
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '课程目录无法读取，原数据未修改。');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    return subscribeCourses(refresh);
  }, [refresh]);

  const active = useMemo(
    () =>
      courses
        .filter((course) => course.status === 'active')
        .sort((a, b) => (a.updatedAt < b.updatedAt ? 1 : -1)),
    [courses],
  );
  const archived = useMemo(
    () => courses.filter((course) => course.status === 'archived'),
    [courses],
  );

  return (
    <div className="space-page courses-page">
      <header className="space-header">
        {/* UX-REGRESSION-FIX v1：课程列表同样提供固定指向教材资料库的返回入口 */}
        <div className="space-header-row">
          <Link className="space-back" href="/knowledge-bases">
            <ArrowLeft size={16} />
            返回教材资料库
          </Link>
        </div>
        <div className="space-header-row">
          <h1>课程</h1>
          <div className="space-card-actions">
            <button
              className="space-button"
              onClick={() => {
                loadDemoCourses();
                setNotice('已载入演示课程（重复载入不产生重复条目）。可在课程详情创建学习会话并进入真实问答。');
              }}
            >
              <Sparkles size={14} />
              载入演示数据
            </button>
            <button className="space-button primary" onClick={() => setCreating(true)}>
              <Plus size={14} />
              新建课程
            </button>
          </div>
        </div>
        <p className="space-description">
          以课程为单位组织大纲、资料与学习约定；大纲进度由学员手动勾选（证据而非自动推断）。
        </p>
      </header>
      <main className="space-content">
        {notice && (
          <div className="space-banner info" role="status">
            {notice}
          </div>
        )}
        {error && (
          <div className="space-banner error" role="alert">
            {error}
          </div>
        )}

        {loading ? (
          <div aria-hidden>
            {[0, 1].map((index) => (
              <div className="space-skeleton" key={index} style={{ height: 76, marginBottom: 10 }} />
            ))}
          </div>
        ) : active.length === 0 ? (
          <div className="space-empty">
            <strong>还没有进行中的课程</strong>
            <span>新建一门课程组织大纲与资料，或载入演示课程。</span>
          </div>
        ) : (
          <div className="space-card-grid">
            {active.map((course) => (
              <CourseCard key={course.id} course={course} onOpen={() => router.push(`/courses/${course.id}`)} />
            ))}
          </div>
        )}

        {archived.length > 0 && (
          <details className="space-group" style={{ marginTop: 18 }}>
            <summary className="space-group-label" style={{ cursor: 'pointer', marginBottom: 0 }}>
              <Archive size={13} strokeWidth={1.7} aria-hidden />
              已归档课程（{archived.length}）
            </summary>
            <div className="space-card-grid" style={{ marginTop: 10 }}>
              {archived.map((course) => (
                <CourseCard key={course.id} course={course} onOpen={() => router.push(`/courses/${course.id}`)} />
              ))}
            </div>
          </details>
        )}

        {creating && (
          <CreateCourseForm
            onClose={() => setCreating(false)}
            onCreated={(id) => {
              setCreating(false);
              router.push(`/courses/${id}`);
            }}
          />
        )}
      </main>
    </div>
  );
}

function CourseCard({ course, onOpen }: { course: StudyCourse; onOpen: () => void }) {
  const summary = syllabusSummary(course);
  return (
    <article className="space-persona-card" style={course.status === 'archived' ? { opacity: 0.7 } : undefined}>
      <Link
        className="space-card-link"
        href={`/courses/${course.id}`}
        aria-label={`打开课程 ${course.name}`}
        onClick={(event) => {
          event.preventDefault();
          onOpen();
        }}
      >
        <div className="space-card-title courses-card-head">
          <span
            aria-hidden
            style={{ width: 10, height: 10, borderRadius: 999, background: COURSE_COLOR_DOT[course.color] }}
          />
          <span className="courses-card-name">{course.name}</span>
          {course.status === 'archived' && <span className="space-chip">已归档</span>}
          <ArrowRight size={15} className="courses-card-arrow" aria-hidden />
        </div>
        <p className="space-card-body">{course.description || '（无简介）'}</p>
        <div className="space-meta-row">
          <span className="space-chip">
            大纲 {summary.covered}/{summary.total}
          </span>
        </div>
        <div className="courses-card-footer">
          {course.resources.length > 0 ? (
            <span className="courses-card-materials" title="课程资料">
              <Layers size={11} strokeWidth={1.8} aria-hidden />
              {course.resources.length} 份资料
            </span>
          ) : (
            <span className="courses-card-empty">尚未附加资料</span>
          )}
        </div>
      </Link>
    </article>
  );
}

function CreateCourseForm({ onClose, onCreated }: { onClose: () => void; onCreated: (id: string) => void }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [color, setColor] = useState<CourseColor>('blue');
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  return (
    <Modal title="新建课程" onClose={onClose}>
      <form
        className="space-form"
        onSubmit={(event) => {
          event.preventDefault();
          if (saving) return;
          setSaving(true);
          try {
            const course = createCourse(name, description, color);
            onCreated(course.id);
          } catch (cause) {
            setError(
              cause instanceof CourseValidationError ? cause.message : '创建失败，请检查输入后重试。',
            );
          } finally {
            setSaving(false);
          }
        }}
      >
        <label>
          名称
          <input
            value={name}
            required
            maxLength={60}
            onChange={(event) => setName(event.target.value)}
            placeholder="例如：七年级数学"
          />
        </label>
        <label>
          简介
          <input
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="这门课覆盖什么内容？"
          />
        </label>
        <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
          <legend className="space-footnote" style={{ padding: 0 }}>
            颜色标记
          </legend>
          <div className="space-card-actions">
            {COURSE_COLORS.map((value) => (
              <button
                type="button"
                key={value}
                aria-label={`颜色 ${value}`}
                aria-pressed={color === value}
                onClick={() => setColor(value)}
                style={{
                  width: 22,
                  height: 22,
                  borderRadius: 999,
                  background: COURSE_COLOR_DOT[value],
                  outline: color === value ? '2px solid var(--ink)' : 'none',
                  outlineOffset: 2,
                }}
              />
            ))}
          </div>
        </fieldset>
        {error && (
          <p className="space-form-error" role="alert">
            {error}
          </p>
        )}
        <div className="space-form-footer">
          <button type="button" className="space-button" onClick={onClose}>
            取消
          </button>
          <button type="submit" className="space-button primary" disabled={saving}>
            {saving ? <Loader2 size={14} className="space-spin" aria-hidden /> : null}
            创建
          </button>
        </div>
      </form>
    </Modal>
  );
}

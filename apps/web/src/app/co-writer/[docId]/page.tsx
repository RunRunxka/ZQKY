import { WritingEditor } from '@/features/writing/WritingEditor';

export const metadata = { title: '智启课源 · 文稿编辑' };

export default async function CoWriterDocPage({ params }: { params: Promise<{ docId: string }> }) {
  const { docId } = await params;
  return <WritingEditor docId={docId} />;
}

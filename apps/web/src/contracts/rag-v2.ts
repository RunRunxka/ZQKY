/** Shared production RAG v2 evidence coordinates; readable mirrors Python null. */
import type { LocatorView, TextbookSelection } from './textbook';
export interface ScopeDocument { documentId: string; documentRevisionId: string; metadataRevisionId: string }
export interface ScopeSnapshot {
  schemaVersion: 2; selection: TextbookSelection; documents: ScopeDocument[];
  embeddingGenerationId: string; scopeHash: string;
}
export interface EvidenceRef {
  evidenceId: string; documentRevisionId: string; normalizedTextSha256: string; charStart: number; charEnd: number;
}
export interface EvidenceReadable { version: 'rag-readable-v1' | 'rag-readable-v2'; text: string; removedImageCount: number }
export interface TextbookEvidence extends EvidenceRef {
  documentId: string; title: string; editionLabel: string; subjectLabel: string; chapterPath: string[];
  text: string; originalFileSha256: string; locator: LocatorView; isSuperseded: boolean; readable?: EvidenceReadable | null;
}

import { useState } from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import type { QuestionContent } from '@/contracts/question-bank';
import { QuestionPreview } from './QuestionPreview';
import { ContentForm, type QuestionFormValue } from './ContentForm';
import { copyContent } from './draft-form';
import { buildTaxonomyIndex } from './taxonomy';

afterEach(cleanup);
const content: QuestionContent = {
  type: 'short_answer', stemMarkdown: '派生旧文本', options: [], answer: {choiceKeys:[],accepted:null,textMarkdown:'2'},
  explanationMarkdown: null, assetIds: [], richContent: {
    version:2, sharedMaterials:[], stemBlocks:[{id:'one',kind:'paragraph',text:'富内容权威题面'}],
    optionBlocks:{}, answerBlocks:[], explanationBlocks:[], assets:[],
    origin:{originalAssetId:'origin',originalSha256:'a'.repeat(64),sourceLocator:{}},
  },
};
it('预览使用富内容权威题面，草稿副本保留且独立', () => {
  const copy = copyContent(content);
  expect(copy.richContent).toEqual(content.richContent);
  expect(copy.richContent).not.toBe(content.richContent);
  render(<QuestionPreview content={copy} />);
  expect(screen.getByText('富内容权威题面')).toBeVisible();
  expect(screen.queryByText('派生旧文本')).toBeNull();
});
it('教师必须明确转换后才可编辑派生文本，新包携带richContent=null', () => {
  function Editor() {
    const [value, setValue] = useState<QuestionFormValue>({content:copyContent(content),metadata:{stageId:'',gradeId:'',subjectId:'math',editionId:'',knowledgeTags:[],difficulty:'unspecified'}});
    return <><ContentForm value={value} onChange={setValue} taxonomy={buildTaxonomyIndex({stages:[],grades:[],subjects:[],editions:[]})} idPrefix="rich" />
      <output data-testid="sent">{JSON.stringify(value.content)}</output></>;
  }
  render(<Editor />);
  expect(screen.getByLabelText('题干')).toBeDisabled();
  fireEvent.click(screen.getByRole('button',{name:'明确转为 Markdown 编辑'}));
  expect(screen.getByLabelText('题干')).toBeEnabled();
  fireEvent.change(screen.getByLabelText('题干'),{target:{value:'教师新文本'}});
  expect(JSON.parse(screen.getByTestId('sent').textContent!)).toMatchObject({stemMarkdown:'教师新文本',richContent:null});
});

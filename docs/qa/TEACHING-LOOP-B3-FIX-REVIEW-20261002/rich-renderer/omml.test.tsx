import { cleanup, render, waitFor } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { RichBlocks } from '@/components/ui/RichContentRenderer';

afterEach(cleanup);
const ns = 'http://schemas.openxmlformats.org/officeDocument/2006/math';

// Diagnosis assertions demonstrate the defect; they are not acceptance assertions.
it.each(['|', ','])('diagnostic: valid multi-base delimiter %s silently loses second base', async (separator) => {
  const xml = `<m:oMath xmlns:m="${ns}"><m:d><m:dPr><m:begChr m:val="("/><m:sepChr m:val="${separator}"/><m:endChr m:val=")"/></m:dPr><m:e><m:r><m:t>x</m:t></m:r></m:e><m:e><m:r><m:t>y</m:t></m:r></m:e></m:d></m:oMath>`;
  const ui = render(<RichBlocks blocks={[{ id: 'delimiter', kind: 'formula', ommlXml: xml }]} />);
  await waitFor(() => expect(ui.container.querySelector('math')).not.toBeNull());
  expect(ui.container.querySelector('math')?.textContent).toBe('(x)');
  expect(ui.container.querySelector('math')?.textContent).not.toContain('y');
  expect(ui.queryByRole('status')).toBeNull();
  expect(ui.container.querySelector('pre')).toHaveTextContent(xml);
});

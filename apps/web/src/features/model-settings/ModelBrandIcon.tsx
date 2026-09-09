import { Cpu } from 'lucide-react';

/** 只按实际模型 ID 识别品牌；未知模型用中性图标，不猜测连接供应商。 */
export function ModelBrandIcon({ modelId }: { modelId?: string }) {
  const id = modelId?.toLowerCase() ?? '';
  const icons: [RegExp, string][] = [
    [/deepseek/, 'deepseek-color'],
    [/claude/, 'anthropic'],
    [/gemini/, 'gemini-color'],
    [/qwen/, 'qwen-color'],
    [/gpt|^o[134](?:-|$)/, 'openai'],
    [/kimi|moonshot/, 'moonshot'],
    [/glm/, 'zhipu-color'],
    [/mistral|mixtral/, 'mistral-color'],
    [/minimax/, 'minimax-color'],
  ];
  const icon = icons.find(([pattern]) => pattern.test(id))?.[1];
  return icon ? (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={`/provider-icons/${icon}.svg`} alt="" width={16} height={16} />
  ) : (
    <Cpu size={16} strokeWidth={1.65} />
  );
}

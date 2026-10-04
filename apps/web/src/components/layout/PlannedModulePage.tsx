import type { PlannedNavigationItem } from '@/contracts/navigation';
import { HomeReturnLink } from './HomeReturnLink';
import { PlannedContent } from './PlannedContent';

/**
 * 共用的“规划中”状态页：模块名称、规划中徽标、用途简介、以后接入的能力
 * 和返回可用工作台的入口。内容来自导航登记表，不显示示例数据或可提交的假操作。
 */
export function PlannedModulePage({ item }: { item: PlannedNavigationItem }) {
  return (
    <PlannedContent className="status-page planned-page">
      <span className="small-badge" data-motion-reveal>规划中</span>
      <h1 data-motion-reveal>{item.label}</h1>
      <p className="planned-summary" data-motion-reveal>{item.plan.summary}</p>
      <section className="planned-capabilities" data-motion-reveal>
        <h2>以后接入的能力</h2>
        <ul>
          {item.plan.capabilities.map((capability) => (
            <li key={capability}>{capability}</li>
          ))}
        </ul>
      </section>
      <p className="planned-note">
        该模块尚未开始开发。目前可以使用教案工作台完成教案编辑、规则填充、草稿与导出。
      </p>
      <HomeReturnLink />
    </PlannedContent>
  );
}

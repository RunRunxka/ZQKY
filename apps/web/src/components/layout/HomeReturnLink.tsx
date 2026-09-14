import Link from 'next/link';
import { HOME_LABEL, HOME_PATH } from '@/services/navigation';

/** 统一的“返回主页”入口：目标与文案都来自导航登记表的唯一主页定义（R-02）。 */
export function HomeReturnLink({ label }: { label?: string }) {
  return (
    <Link className="button primary" href={HOME_PATH}>
      {label ?? `返回${HOME_LABEL}`}
    </Link>
  );
}

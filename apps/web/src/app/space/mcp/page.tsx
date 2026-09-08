import { redirect } from 'next/navigation';

/**
 * 参考仓库 /space/mcp 为独立管理页；按本项目既定决策（MCP 管理只在设置，
 * 不复制第二套管理），旧入口统一重定向到设置的 MCP 区。
 */
export default function SpaceMcpPage() {
  redirect('/settings#mcp');
}

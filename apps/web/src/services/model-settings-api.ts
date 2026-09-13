/** 模型设置的 HTTP 封装：全部经 /api/v1 同源代理，不直接访问外部主机。 */

import { apiRequest } from './api-client';
import type {
  AuthActionResult,
  AuthStatus,
  ConnectionInput,
  DiscoveryResult,
  ModelCatalog,
  ModelConnectionView,
  ModelProfileView,
  ModelProviderDirectory,
  ModelTestResult,
  ProfileInput,
} from '@/contracts/model-settings';

export function listConnections(): Promise<ModelConnectionView[]> {
  return apiRequest<ModelConnectionView[]>('/model-connections');
}

export function createConnection(input: ConnectionInput): Promise<ModelConnectionView> {
  return apiRequest<ModelConnectionView>('/model-connections', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(input),
  });
}

export function updateConnection(id: string, input: ConnectionInput): Promise<ModelConnectionView> {
  return apiRequest<ModelConnectionView>(`/model-connections/${id}`, {
    method: 'PUT',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(input),
  });
}

export function deleteConnection(id: string, revision?: number): Promise<void> {
  return apiRequest<void>(
    `/model-connections/${id}${revision === undefined ? '' : `?expectedRevision=${revision}`}`,
    { method: 'DELETE' },
  );
}

export function listProfiles(): Promise<ModelProfileView[]> {
  return apiRequest<ModelProfileView[]>('/model-profiles');
}

export function createProfile(input: ProfileInput): Promise<ModelProfileView> {
  return apiRequest<ModelProfileView>('/model-profiles', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(input),
  });
}

export function updateProfile(id: string, input: ProfileInput): Promise<ModelProfileView> {
  return apiRequest<ModelProfileView>(`/model-profiles/${id}`, {
    method: 'PUT',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(input),
  });
}

export function deleteProfile(id: string, revision?: number): Promise<void> {
  return apiRequest<void>(
    `/model-profiles/${id}${revision === undefined ? '' : `?expectedRevision=${revision}`}`,
    { method: 'DELETE' },
  );
}

export interface ProfileTestInput {
  stream?: boolean;
  prompt?: string;
  maxOutputTokens?: number;
  params?: Record<string, number>;
}

export const loadModelCatalog = () => apiRequest<ModelCatalog>('/model-catalog');
export const loadProviderDirectory = () => apiRequest<ModelProviderDirectory>('/model-providers');
export const discoverModels = (id: string) =>
  apiRequest<DiscoveryResult>(`/model-connections/${id}/models`);
export const setDefaultModel = (modelProfileId: string | null, expectedRevision: number) =>
  apiRequest<ModelCatalog>('/model-defaults', {
    method: 'PUT',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ modelProfileId, expectedRevision }),
  });
export function notifyModelCatalogChanged() {
  window.dispatchEvent(new Event('model-catalog-changed'));
}

export function testProfile(id: string, input: ProfileTestInput = {}): Promise<ModelTestResult> {
  return apiRequest<ModelTestResult>(`/model-profiles/${id}/test`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(input),
  });
}

// --- 认证生命周期（D9/D10）------------------------------------------------

export const getAuthStatus = (connectionId: string) =>
  apiRequest<AuthStatus>(`/model-connections/${connectionId}/auth`);
export const startAuth = (connectionId: string) =>
  apiRequest<AuthActionResult>(`/model-connections/${connectionId}/auth/start`, { method: 'POST' });
export const cancelAuth = (connectionId: string) =>
  apiRequest<AuthActionResult>(`/model-connections/${connectionId}/auth/cancel`, { method: 'POST' });
export const logoutAuth = (connectionId: string) =>
  apiRequest<AuthActionResult>(`/model-connections/${connectionId}/auth/logout`, { method: 'POST' });

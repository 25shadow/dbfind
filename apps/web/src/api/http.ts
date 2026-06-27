export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      ...(!(init?.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
      ...init?.headers
    }
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(parseApiErrorMessage(message, response.status) || `请求失败：${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

function parseApiErrorMessage(message: string, status: number) {
  if (!message) {
    return "";
  }

  if (status === 504 || /504 Gateway Time-out/i.test(message)) {
    return "服务器预览超时：查询或生成预览耗时太久，请稍后重试或缩小数据范围。";
  }

  if (/<html[\s>]/i.test(message) || /<body[\s>]/i.test(message)) {
    return `服务器返回了网页错误：HTTP ${status}`;
  }

  try {
    const data = JSON.parse(message) as { detail?: unknown };
    if (typeof data.detail === "string") {
      return data.detail;
    }
  } catch {
    return message;
  }

  return message;
}

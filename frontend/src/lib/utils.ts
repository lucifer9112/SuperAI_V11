import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export const cn = (...i: ClassValue[]) => twMerge(clsx(i));
export const sleep = (ms: number) => new Promise<void>(r => setTimeout(r, ms));
export const shortId = () => Math.random().toString(36).slice(2, 10);
export const formatMs = (ms: number) => ms < 1000 ? `${Math.round(ms)}ms` : `${(ms/1000).toFixed(1)}s`;
export const formatUptime = (s: number) => {
  if (s < 60)   return `${Math.floor(s)}s`;
  if (s < 3600) return `${Math.floor(s/60)}m`;
  return `${Math.floor(s/3600)}h ${Math.floor((s%3600)/60)}m`;
};

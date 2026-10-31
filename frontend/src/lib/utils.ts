import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

// Joins class names; when two Tailwind classes clash (p-2 then p-4), the later one wins
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
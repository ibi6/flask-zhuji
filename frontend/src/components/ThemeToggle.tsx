// 主题切换按钮

import { Moon, Sun } from "lucide-react";
import { useTheme } from "@/store/theme";

export function ThemeToggle({ className = "" }: { className?: string }) {
  const { theme, toggleTheme } = useTheme();
  const nextLabel = theme === "dark" ? "浅色" : "深色";

  return (
    <button
      type="button"
      onClick={toggleTheme}
      className={`theme-toggle ${className}`}
      title={`切换到${nextLabel}主题`}
      aria-label={`切换到${nextLabel}主题`}
    >
      {theme === "dark" ? <Sun className="h-4 w-4" aria-hidden /> : <Moon className="h-4 w-4" aria-hidden />}
      <span className="hidden sm:inline">{nextLabel}</span>
    </button>
  );
}

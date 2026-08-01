/** 客户端 CSV 导出（Excel 可直接打开，UTF-8 BOM） */

export function downloadCsv(filename: string, headers: string[], rows: string[][]): void {
  const escape = (value: string) => `"${value.replace(/"/g, '""')}"`;
  const lines = [headers, ...rows].map((row) => row.map((cell) => escape(String(cell ?? ""))).join(","));
  const bom = "\uFEFF";
  const blob = new Blob([bom + lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename.endsWith(".csv") ? filename : `${filename}.csv`;
  anchor.click();
  URL.revokeObjectURL(url);
}

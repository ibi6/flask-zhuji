// CSV 导出工具测试

import { beforeEach, describe, expect, it, vi } from "vitest";
import { downloadCsv } from "@/lib/exportCsv";

describe("downloadCsv", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("生成带 UTF-8 BOM 的 CSV 并触发下载", () => {
    let capturedBlob: Blob | undefined;
    const createObjectURL = vi.fn((blob: Blob) => {
      capturedBlob = blob;
      return "blob:test";
    });
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", { createObjectURL, revokeObjectURL });

    const anchor = {
      href: "",
      download: "",
      click: vi.fn(),
    } as unknown as HTMLAnchorElement;
    vi.spyOn(document, "createElement").mockReturnValue(anchor);

    downloadCsv("hostguard-alerts.csv", ["ID", "摘要"], [["a1", "测试,告警"]]);

    expect(capturedBlob?.type).toBe("text/csv;charset=utf-8;");
    expect(anchor.download).toBe("hostguard-alerts.csv");
    expect(anchor.click).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:test");
  });

  it("自动补全 .csv 后缀", () => {
    const createObjectURL = vi.fn(() => "blob:test");
    vi.stubGlobal("URL", { createObjectURL, revokeObjectURL: vi.fn() });
    const anchor = { href: "", download: "", click: vi.fn() } as unknown as HTMLAnchorElement;
    vi.spyOn(document, "createElement").mockReturnValue(anchor);

    downloadCsv("export", ["列"], [["值"]]);
    expect(anchor.download).toBe("export.csv");
  });
});

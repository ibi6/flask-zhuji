// flux-field 风格动态背景：渐变光球 + 网格 + 噪点

export function FluxScene() {
  return (
    <div className="flux-scene" aria-hidden>
      <div className="flux-orb flux-orb--a" />
      <div className="flux-orb flux-orb--b" />
      <div className="flux-orb flux-orb--c" />
      <div className="flux-grid" />
      <div className="flux-noise" />
      <div className="flux-backdrop" />
    </div>
  );
}

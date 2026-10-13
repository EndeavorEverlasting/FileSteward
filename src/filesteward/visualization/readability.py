"""Material-world refinement: task hierarchy, legible prose, reachable controls."""


def render_readability_css() -> str:
    return """
html,body{font-family:var(--fs-font-sans);color-scheme:light dark;}
.app{grid-template-rows:auto auto auto auto auto;overflow-x:clip;}
.fs-type-body,.shell .sub,.shell .class-legend-meaning,.shell .next-action span,.atlas-scene-panel span,.mode-brief,.chamber-approval dd,.decision-chamber{font-family:var(--fs-font-sans);font-size:.875rem;line-height:1.5;letter-spacing:normal;}
.shell{padding:1.2rem 1.5rem;}
.shell .brand-title{font-size:1.6rem;line-height:1.25;letter-spacing:.015em;text-shadow:none;}
.shell .sub{margin-top:.4rem;max-width:85ch;}
.evidence-guide{margin-top:.85rem;font-size:.875rem;}
.evidence-guide summary{cursor:pointer;min-height:32px;display:list-item;}
.metrics{padding:.75rem 1.5rem;gap:0;background:var(--fs-bg-shell);}
.metric{border:0;border-radius:0;background:transparent;padding:.45rem 1rem;border-right:1px solid var(--fs-border-subtle);}
.metric:last-child{border-right:0;}
.metric b{font-size:1.2rem;line-height:1.4;}
.metric span{font-size:.8rem;line-height:1.4;}
.nav-row{padding:.8rem;min-height:64px;}
.nav-name{font-size:.95rem;line-height:1.35;}
.nav-meta{font-family:var(--fs-font-sans);font-size:.8rem;line-height:1.5;}
.workspace{height:auto;align-items:start;}
.workspace .pane{height:auto;max-height:52rem;overflow:auto;box-sizing:border-box;}
.workspace .map-pane{max-height:none;overflow:visible;}
.storage-stage{height:clamp(38rem,72vh,52rem);min-height:38rem;}
.scene-script-index{margin:1rem 1.5rem;}
.pane-scene-btn{min-height:40px;}
.next-action{min-height:44px;}
.next-action span{font-family:var(--fs-font-sans);font-size:.85rem;line-height:1.4;}
.chamber-confirm{min-height:44px;}
.decision-chamber{max-width:calc(100vw - 24px);box-sizing:border-box;}
.sector-card,.focus-chamber{color:var(--fs-text-primary);}
.sector-state,.sector-path{font-size:.8rem;}
.focus-identity h3{letter-spacing:-.03em;line-height:1.08;}
@media(max-width:799px){
  .shell{padding:1rem;}
  .shell .brand-title{font-size:1.3rem;}
  .metrics{grid-template-columns:repeat(2,minmax(0,1fr));padding:.5rem;}
  .metric{min-height:72px;border:0;padding:.65rem;}
  .metrics .metric:last-child{grid-column:1/-1;min-height:56px;}
  .workspace,.workspace[data-scene="overview"],.workspace[data-scene="focus"],.workspace[data-open-decision-scene]{display:flex;flex-direction:column;height:auto;align-items:stretch;}
  .workspace .pane{height:auto;max-height:none;}
  .workspace .navigator-pane{position:static!important;inset:auto!important;display:block!important;visibility:visible!important;opacity:1!important;pointer-events:auto!important;transform:none!important;max-height:24rem;overflow:auto;order:0;}
  .workspace .navigator-pane .nav,.workspace .navigator-pane .filters,.workspace .navigator-pane .search-label{display:block!important;}
  .workspace .map-pane{order:1;}
  .workspace .inspector-pane{position:static!important;inset:auto!important;display:none!important;visibility:visible;opacity:1;pointer-events:auto;order:2;max-height:32rem;overflow:auto;}
  .workspace[data-decision-open="true"] .inspector-pane{display:block!important;}
  .storage-stage{height:46rem;min-height:46rem;}
  .sector-grid{gap:.5rem;}
  .sector-card{padding:.6rem;grid-template-columns:minmax(0,1fr);grid-template-rows:auto auto 1fr;}
  .sector-order{font-size:.65rem;}
  .sector-title{font-size:.85rem;overflow-wrap:anywhere;white-space:normal;}
  .sector-size{font-size:1.1rem;}
  .sector-path{display:none;}
  .sector-state{font-size:.7rem;}
  .scene-script-index{margin:.75rem;}
  .scene-script-index ol{grid-template-columns:1fr;}
}
@media(prefers-reduced-motion:reduce){.workspace,.storage-stage,.sector-card,.decision-chamber{animation:none!important;transition:none!important;}}
@media(forced-colors:active){.metric,.scene-script-index,.script-impact{background:Canvas;color:CanvasText;}.metric:focus-visible{outline:2px solid Highlight;}}
"""

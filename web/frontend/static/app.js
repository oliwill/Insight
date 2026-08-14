/* Insight 前端脚本：Markdown 报告渲染 + 图表链接转换 */
(function () {
  function renderMarkdown() {
    document.querySelectorAll('script[type="text/markdown"]').forEach(function (el) {
      const host = document.querySelector(el.dataset.host);
      if (!host) return;
      // 报告内图表相对路径（../../Charts/x.png）→ 用户媒体服务
      const md = el.textContent.replace(
        /!\[([^\]]*)\]\(\.\.\/\.\.\/Charts\/([^)]+)\)/g,
        '![$1](/stocks/media/charts/$2)'
      );
      host.innerHTML = marked.parse(md);
    });
  }

  document.addEventListener('DOMContentLoaded', renderMarkdown);
  document.body.addEventListener('htmx:afterSwap', renderMarkdown);
})();

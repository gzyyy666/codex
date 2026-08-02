const notepad = require("../../utils/freeformNotepad");
const candidates = require("../../utils/freeformCandidates");
const movementPreview = require("../../utils/movementPreview");

Component({
  properties: { visible: { type: Boolean, value: true } },
  data: { open: false, text: "", candidates: [], candidatesLoading: false, candidatesCollapsed: false, detailOpen: false, detailLoading: false, detailError: "", detailMovement: null, detailHistory: [] },
  observers: {
    visible(next, previous) {
      // The inline Archive editor and the floating Dock share one local key.
      // Refresh when the Dock becomes visible so it never shows a stale copy
      // after text was entered in the other editor.
      if (next && next !== previous) this.refresh();
    }
  },
  lifetimes: {
    attached() { this.refresh(); },
    detached() { this.cancelCandidateSearch(); }
  },
  pageLifetimes: {
    show() { this.refresh(); },
    hide() { this.cancelCandidateSearch(); }
  },
  methods: {
    refresh() {
      this.noteText = notepad.load();
      this.setData({ text: this.noteText, candidates: [] });
      this.scheduleCandidateSearch(this.noteText);
    },
    flush() {
      notepad.save(String(this.noteText || ""));
      this.setData({ text: String(this.noteText || "") });
    },
    toggle() {
      if (this.data.open) {
        this.flush();
        this.setData({ open: false });
        return;
      }
      this.refresh();
      this.setData({ open: true });
    },
    persist(value) {
      this.noteText = String(value == null ? "" : value);
      // Persist on every input. Keep the component value in sync as well: the
      // Dock can be hidden/revealed by scrolling while its textarea is alive,
      // so a later render must not reapply the pre-edit value.
      notepad.save(this.noteText);
      if (this.data.text !== this.noteText) this.setData({ text: this.noteText });
      this.scheduleCandidateSearch(this.noteText);
    },
    onInput(event) { this.persist(event.detail && event.detail.value); },
    onChange(event) { this.persist(event.detail && event.detail.value); },
    onBlur(event) {
      const value = event && event.detail && event.detail.value != null ? event.detail.value : this.noteText;
      this.persist(value);
    },
    scheduleCandidateSearch(text) {
      this.cancelCandidateSearch();
      if (!String(text || "").trim()) {
        this.setData({ candidates: [], candidatesLoading: false });
        return;
      }
      this.setData({ candidatesLoading: true, candidatesCollapsed: false });
      this.candidateTimer = setTimeout(() => {
        const request = ++this.candidateRequest;
        candidates.detect(text).then(items => {
          if (request !== this.candidateRequest) return;
          this.setData({ candidates: items, candidatesLoading: false });
          Promise.all(items.map(item => movementPreview.load(item.movement_id))).then(previews => {
            if (request !== this.candidateRequest) return;
            this.setData({ candidates: items.map((item, index) => {
              const history = previews[index] && previews[index].history || [];
              const latest = history[0];
              return latest ? { ...item, previewDate: latest.date, previewSummary: movementPreview.summarize(latest), previewHistory: history } : item;
            }) });
          });
        });
      }, 180);
    },
    cancelCandidateSearch() {
      if (this.candidateTimer) clearTimeout(this.candidateTimer);
      this.candidateTimer = null;
      this.candidateRequest = (this.candidateRequest || 0) + 1;
    },
    toggleCandidates() { this.setData({ candidatesCollapsed: !this.data.candidatesCollapsed }); },
    openCandidate(event) {
      const movementId = event.currentTarget.dataset.id;
      if (!movementId) return;
      this.setData({ detailOpen: true, detailLoading: true, detailError: "", detailMovement: null, detailHistory: [] });
      movementPreview.load(movementId).then(detail => {
        this.setData({ detailLoading: false, detailError: detail.error, detailMovement: detail.movement, detailHistory: detail.history });
      });
    },
    closeDetail() {
      this.setData({ detailOpen: false });
    },
    noop() {},
    copy() {
      if (!this.noteText) { wx.showToast({ title: "暂无可复制内容", icon: "none" }); return; }
      wx.setClipboardData({ data: this.noteText, success: () => wx.showToast({ title: "已复制全部", icon: "success" }) });
    },
    clear() {
      wx.showModal({ title: "清空训练记录？", content: "只清空当前 TRAINING NOTE，不会影响正式训练记录。", confirmText: "清空", confirmColor: "#a33d31", success: result => {
        if (!result.confirm) return;
        notepad.clear();
        this.noteText = "";
        this.cancelCandidateSearch();
        this.setData({ text: "", candidates: [], candidatesLoading: false });
      } });
    }
  }
});

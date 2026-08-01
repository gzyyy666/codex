const notepad = require("../../utils/freeformNotepad");

Component({
  properties: { visible: { type: Boolean, value: true } },
  data: { open: false, text: "" },
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
    detached() { this.flush(); }
  },
  pageLifetimes: {
    show() { this.refresh(); },
    hide() { this.flush(); }
  },
  methods: {
    refresh() {
      this.noteText = notepad.load();
      this.setData({ text: this.noteText });
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
    },
    onInput(event) { this.persist(event.detail && event.detail.value); },
    onChange(event) { this.persist(event.detail && event.detail.value); },
    onBlur(event) {
      const value = event && event.detail && event.detail.value != null ? event.detail.value : this.noteText;
      this.persist(value);
    },
    copy() {
      if (!this.noteText) { wx.showToast({ title: "暂无可复制内容", icon: "none" }); return; }
      wx.setClipboardData({ data: this.noteText, success: () => wx.showToast({ title: "已复制全部", icon: "success" }) });
    },
    clear() {
      wx.showModal({ title: "清空训练记录？", content: "只清空当前 TRAINING NOTE，不会影响正式训练记录。", confirmText: "清空", confirmColor: "#a33d31", success: result => {
        if (!result.confirm) return;
        notepad.clear();
        this.noteText = "";
        this.setData({ text: "" });
      } });
    }
  }
});

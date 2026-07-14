const notepad = require("../../utils/freeformNotepad");

Component({
  properties: { visible: { type: Boolean, value: true } },
  data: { open: false, text: "" },
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
    onInput(event) { this.noteText = event.detail.value; notepad.save(this.noteText); },
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

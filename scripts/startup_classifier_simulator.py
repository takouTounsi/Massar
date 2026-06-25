import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import json
from dataclasses import asdict

from shared.application.router import (
    start_session,
    submit_answer,
    AnswerRequest,
    RouterError,
    TranscriptEntry,
)
from shared.application.startup_classifier import INDUSTRIES_BY_KEY, LLMClassifier
from shared.llm.gemini_provider import gemini_classify


DEFAULT_CLASSIFIER = LLMClassifier(gemini_classify)


class StartupClassifierSimulator(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Startup Phase Classifier - Frontend Simulator")
        self.geometry("1100x700")
        
        # State variables
        self.current_industry_key = None
        self.current_node_id = None
        self.current_transcript = []
        self.dummy_classifier = DEFAULT_CLASSIFIER
        self.current_payload = None

        self._build_ui()

    def _build_ui(self):
        top_frame = ttk.Frame(self, padding=10)
        top_frame.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(top_frame, text="Select Industry:").pack(side=tk.LEFT, padx=5)
        
        self.industry_var = tk.StringVar()
        industry_choices = [f"{k} - {v.name}" for k, v in INDUSTRIES_BY_KEY.items()]
        self.industry_combo = ttk.Combobox(top_frame, textvariable=self.industry_var, values=industry_choices, state="readonly", width=40)
        if industry_choices:
            self.industry_combo.current(0)
        self.industry_combo.pack(side=tk.LEFT, padx=5)

        ttk.Button(top_frame, text="Start Session", command=self.cmd_start_session).pack(side=tk.LEFT, padx=10)

        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        left_frame = ttk.Frame(paned, padding=10, relief=tk.SUNKEN)
        paned.add(left_frame, weight=1)

        self.lbl_node_id = ttk.Label(left_frame, text="Node ID: ---", foreground="gray")
        self.lbl_node_id.pack(anchor=tk.W)

        self.lbl_question = ttk.Label(left_frame, text="Welcome! Select an industry and click Start.", font=("Helvetica", 14, "bold"), wraplength=450)
        self.lbl_question.pack(anchor=tk.W, pady=(10, 5))

        self.lbl_explanation = ttk.Label(left_frame, text="", font=("Helvetica", 11, "italic"), wraplength=450, foreground="blue")
        self.lbl_explanation.pack(anchor=tk.W, pady=(0, 15))

        self.options_frame = ttk.Frame(left_frame)
        self.options_frame.pack(anchor=tk.W, fill=tk.X)
        self.radio_var = tk.IntVar(value=-1)

        self.text_frame = ttk.Frame(left_frame)
        self.text_frame.pack(anchor=tk.W, fill=tk.X, pady=15)
        ttk.Label(self.text_frame, text="OR Type Free-Text Answer:").pack(anchor=tk.W)
        self.txt_free_input = tk.Text(self.text_frame, height=4, width=55)
        self.txt_free_input.pack(anchor=tk.W, pady=5)

        self.btn_submit = ttk.Button(left_frame, text="Submit Answer", command=self.cmd_submit_answer, state=tk.DISABLED)
        self.btn_submit.pack(anchor=tk.W, pady=10)

        self.lbl_result = ttk.Label(left_frame, text="", font=("Helvetica", 12, "bold"), foreground="green", wraplength=450)
        self.lbl_result.pack(anchor=tk.W, pady=10)

        right_frame = ttk.Frame(paned, padding=10, relief=tk.SUNKEN)
        paned.add(right_frame, weight=1)
        
        ttk.Label(right_frame, text="Frontend JSON Payload Logs", font=("Helvetica", 12, "bold")).pack(anchor=tk.W)
        self.log_text = scrolledtext.ScrolledText(right_frame, width=50, font=("Consolas", 9), bg="#1e1e1e", fg="#d4d4d4")
        self.log_text.pack(fill=tk.BOTH, expand=True, pady=5)

    def log_json(self, title, obj):
        self.log_text.insert(tk.END, f"\n--- {title} ---\n")
        try:
            pretty = json.dumps(asdict(obj), indent=2)
            self.log_text.insert(tk.END, pretty + "\n")
        except Exception:
            self.log_text.insert(tk.END, str(obj) + "\n")
        self.log_text.see(tk.END)

    def cmd_start_session(self):
        selection = self.industry_var.get()
        if not selection:
            return
        
        self.current_industry_key = selection.split(" - ")[0]
        self.current_transcript = []
        self.log_text.delete(1.0, tk.END)

        try:
            payload = start_session(self.current_industry_key)
            self.log_json("SERVER SENT: QUESTION PAYLOAD", payload)
            self.render_payload(payload)
        except RouterError as e:
            messagebox.showerror("Router Error", e.message)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def render_payload(self, payload):
        self.current_payload = payload
        self.current_node_id = payload.node_id
        self.lbl_node_id.config(text=f"Node ID: {payload.node_id}")
        self.lbl_result.config(text="")
        
        for widget in self.options_frame.winfo_children():
            widget.destroy()
        self.radio_var.set(-1)
        self.txt_free_input.delete(1.0, tk.END)

        if payload.is_terminal:
            self.lbl_question.config(text=f"🏁 PHASE: {payload.phase}")
            self.lbl_explanation.config(text="")
            self.lbl_result.config(text=payload.result_text)
            self.text_frame.pack_forget()
            self.btn_submit.config(state=tk.DISABLED)
            messagebox.showinfo("Session Complete", "You have reached a terminal result phase!")
            
        else:
            self.lbl_question.config(text=payload.question)
            self.lbl_explanation.config(text=payload.explanation if payload.explanation else "")
            
            for opt in payload.options:
                rb = ttk.Radiobutton(self.options_frame, text=opt.text, variable=self.radio_var, value=opt.index)
                rb.pack(anchor=tk.W, pady=2)
            
            if payload.allow_free_text:
                self.text_frame.pack(anchor=tk.W, fill=tk.X, pady=15)
            else:
                self.text_frame.pack_forget()

            self.btn_submit.config(state=tk.NORMAL)

    def cmd_submit_answer(self):
        free_text = self.txt_free_input.get(1.0, tk.END).strip()
        selected_idx = self.radio_var.get()
        
        is_free_text_provided = bool(free_text)
        is_option_selected = (selected_idx != -1)

        if is_free_text_provided and is_option_selected:
            messagebox.showwarning("Ambiguous", "Please either select an option OR type text, not both.")
            return
        if not is_free_text_provided and not is_option_selected:
            messagebox.showwarning("Incomplete", "Please select an option or type an answer.")
            return

        req = AnswerRequest(
            session_industry_key=self.current_industry_key,
            node_id=self.current_node_id,
            selected_option_index=selected_idx if is_option_selected else None,
            free_text=free_text if is_free_text_provided else None,
            transcript_so_far=self.current_transcript
        )
        
        self.log_json("FRONTEND SENDS: ANSWER REQUEST", req)

        try:
            new_payload = submit_answer(req, classifier=self.dummy_classifier)
            self.log_json("SERVER RETURNED PAYLOAD", new_payload)
            
            if getattr(new_payload, 'transcript', None) is not None:
                self.current_transcript = [TranscriptEntry(**t) if isinstance(t, dict) else t for t in new_payload.transcript]
            else:
                chosen_text = free_text if is_free_text_provided else self.current_payload.options[selected_idx].text
                self.current_transcript.append(TranscriptEntry(
                    node_id=self.current_node_id,
                    question=self.current_payload.question,
                    chosen_answer_text=chosen_text
                ))

            self.render_payload(new_payload)

        except RouterError as e:
            messagebox.showerror("Router Error", f"[{e.code}] {e.message}")
        except Exception as e:
            messagebox.showerror("Error", str(e))


if __name__ == "__main__":
    app = StartupClassifierSimulator()
    app.mainloop()

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import threading, time, math, json
from dataclasses import dataclass, asdict
from typing import Optional

try:
    from pynput import keyboard, mouse
    from pynput.keyboard import Key, KeyCode
except ImportError:
    raise SystemExit("Missing dependency. Run: pip install -r requirements.txt")

@dataclass
class Action:
    kind: str
    value: str
    delay_ms: int = 10
    enabled: bool = True
    x: Optional[int] = None
    y: Optional[int] = None
    duration_ms: int = 0

class SwiftMacroPro:
    def __init__(self, root):
        self.root = root
        root.title("SwiftMacro Pro")
        root.geometry("1100x740")
        root.minsize(920, 620)
        self.actions = []
        self.recording = False
        self.playing = False
        self.stop_event = threading.Event()
        self.last_action_time = 0.0
        self.kb = keyboard.Controller()
        self.ms = mouse.Controller()
        self.record_kb_listener = None
        self.record_mouse_listener = None
        self.global_listener = None
        self.record_held = set()
        self.pressed_now = set()
        self.start_hotkey = tk.StringVar(value="f6")
        self.stop_hotkey = tk.StringVar(value="f7")
        self.emergency_hotkey = tk.StringVar(value="f12")
        self.run_mode = tk.StringVar(value="Toggle / hotkey")
        self.hold_key = tk.StringVar(value="space")
        self.trigger_key = tk.StringVar(value="None")
        self.repeat_count = tk.StringVar(value="1")
        self.loop = tk.BooleanVar(value=False)
        self.start_delay = tk.IntVar(value=0)
        self.repeat_interval = tk.IntVar(value=0)
        self.action_limit = tk.IntVar(value=0)
        self.speed = tk.DoubleVar(value=1.0)
        self.angle = tk.IntVar(value=0)
        self.distance = tk.IntVar(value=100)
        self.angle_duration = tk.IntVar(value=100)
        self.status = tk.StringVar(value="Ready")
        self._build()
        self._start_global_listener()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _build(self):
        style = ttk.Style()
        try: style.theme_use("clam")
        except tk.TclError: pass
        style.configure("Title.TLabel", font=("Segoe UI", 19, "bold"))
        style.configure("Section.TLabel", font=("Segoe UI", 11, "bold"))
        shell = ttk.Frame(self.root, padding=14); shell.pack(fill="both", expand=True)
        head = ttk.Frame(shell); head.pack(fill="x")
        ttk.Label(head, text="SwiftMacro Pro", style="Title.TLabel").pack(side="left")
        ttk.Label(head, text="High-speed keyboard + mouse macro studio", foreground="#3982d6").pack(side="left", padx=14, pady=(8,0))
        ttk.Label(shell, textvariable=self.status, foreground="#16814b").pack(anchor="w", pady=(8,8))

        toolbar = ttk.Frame(shell); toolbar.pack(fill="x", pady=(0,10))
        for label, cmd in [
            ("● Record", self.start_recording), ("■ Stop", self.stop_all),
            ("▶ Play", self.play), ("＋ Key", self.add_key), ("＋ Click", self.add_click),
            ("＋ Angle Move", self.add_angle), ("＋ Wait", self.add_wait)
        ]:
            ttk.Button(toolbar, text=label, command=cmd).pack(side="left", padx=(0,5))

        paned = ttk.Panedwindow(shell, orient="horizontal"); paned.pack(fill="both", expand=True)
        left = ttk.Frame(paned, padding=(0,0,10,0)); right = ttk.Frame(paned, padding=(10,0,0,0))
        paned.add(left, weight=3); paned.add(right, weight=2)
        ttk.Label(left, text="Action sequence", style="Section.TLabel").pack(anchor="w", pady=(0,6))
        cols = ("enabled","type","value","delay","duration")
        self.tree = ttk.Treeview(left, columns=cols, show="headings", height=20)
        for col, label, width in [("enabled","On",42),("type","Action",120),("value","Key / details",300),("delay","Delay ms",75),("duration","Move time ms",95)]:
            self.tree.heading(col,text=label); self.tree.column(col,width=width,anchor="center" if col in ("enabled","delay","duration") else "w")
        self.tree.pack(fill="both",expand=True)
        self.tree.bind("<Double-1>", self.edit_value)
        row = ttk.Frame(left); row.pack(fill="x", pady=8)
        for label, cmd in [("Enable/disable",self.toggle_action),("Edit delay",self.edit_delay),("Edit move time",self.edit_duration),("↑",lambda:self.move(-1)),("↓",lambda:self.move(1)),("Delete",self.delete_action)]:
            ttk.Button(row,text=label,command=cmd).pack(side="left",padx=(0,5))

        ttk.Label(right,text="Run behaviour",style="Section.TLabel").pack(anchor="w",pady=(0,7))
        self.row(right,"Mode",ttk.Combobox(right,textvariable=self.run_mode,state="readonly",width=23,values=["Toggle / hotkey","While key is held"]))
        self.row(right,"Hold key",ttk.Entry(right,textvariable=self.hold_key,width=14))
        ttk.Label(right,text="In 'While key is held' mode, the macro runs/repeats only while the chosen key stays down. Releasing it stops playback.",wraplength=330).pack(anchor="w",pady=(0,6))
        self.row(right,"Start hotkey",ttk.Entry(right,textvariable=self.start_hotkey,width=14))
        self.row(right,"Stop hotkey",ttk.Entry(right,textvariable=self.stop_hotkey,width=14))
        self.row(right,"Emergency stop",ttk.Entry(right,textvariable=self.emergency_hotkey,width=14))
        self.row(right,"Start trigger key",ttk.Combobox(right,textvariable=self.trigger_key,state="readonly",width=14,values=["None","space","shift","ctrl","alt","w","a","s","d","e","q","r","f","1","2","3"]))
        self.row(right,"Repeat count",ttk.Entry(right,textvariable=self.repeat_count,width=14))
        ttk.Checkbutton(right,text="Loop until stopped (or hold key released)",variable=self.loop).pack(anchor="w",pady=5)
        self.row(right,"Start delay (ms)",ttk.Spinbox(right,from_=0,to=60000,textvariable=self.start_delay,width=12))
        self.row(right,"Repeat interval (ms)",ttk.Spinbox(right,from_=0,to=60000,textvariable=self.repeat_interval,width=12))
        self.row(right,"Action limit / run (0=unlimited)",ttk.Spinbox(right,from_=0,to=100000,textvariable=self.action_limit,width=12))
        ttk.Label(right,text="Playback speed multiplier").pack(anchor="w",pady=(6,0))
        ttk.Scale(right,from_=0.05,to=8.0,variable=self.speed,orient="horizontal").pack(fill="x")
        self.speed_label=ttk.Label(right,text="1.00×"); self.speed_label.pack(anchor="e")
        self.speed.trace_add("write",lambda *_:self.speed_label.config(text=f"{self.speed.get():.2f}×"))

        ttk.Separator(right).pack(fill="x",pady=10)
        ttk.Label(right,text="Timed 0–360° mouse movement",style="Section.TLabel").pack(anchor="w")
        ttk.Label(right,text="Angle 0° moves right, 90° down, 180° left, 270° up. Duration controls how long the movement takes.",wraplength=330).pack(anchor="w",pady=(3,6))
        self.row(right,"Angle (°)",ttk.Spinbox(right,from_=0,to=360,textvariable=self.angle,width=10))
        self.row(right,"Distance (pixels)",ttk.Spinbox(right,from_=1,to=5000,textvariable=self.distance,width=10))
        self.row(right,"Angle duration (ms)",ttk.Spinbox(right,from_=0,to=60000,textvariable=self.angle_duration,width=10))
        ttk.Button(right,text="Add timed angle move",command=self.add_angle).pack(fill="x",pady=(4,8))
        ttk.Separator(right).pack(fill="x",pady=8)
        ttk.Label(right,text="Hotkeys",style="Section.TLabel").pack(anchor="w")
        ttk.Label(right,text="Default: F6 play · F7 stop · F12 emergency stop\n0 ms angle duration = instant move. Try 10–100 ms for a quick movement.",wraplength=330,justify="left").pack(anchor="w",pady=(4,0))
        bottom = ttk.Frame(shell); bottom.pack(fill="x",pady=(10,0))
        ttk.Button(bottom,text="Clear actions",command=self.clear).pack(side="left")
        ttk.Button(bottom,text="Save profile…",command=self.save).pack(side="right")
        ttk.Button(bottom,text="Load profile…",command=self.load).pack(side="right",padx=6)

    def row(self,parent,label,widget):
        r=ttk.Frame(parent); r.pack(fill="x",pady=3)
        ttk.Label(r,text=label).pack(side="left")
        widget.pack(side="right")

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for i,a in enumerate(self.actions):
            self.tree.insert("","end",iid=str(i),values=("✓" if a.enabled else "—",a.kind,a.value,a.delay_ms,a.duration_ms if a.kind=="Mouse Relative" else "—"))

    def selected(self):
        s=self.tree.selection()
        return int(s[0]) if s else None

    def key_name(self,key):
        if isinstance(key,KeyCode): return key.char.lower() if key.char else str(key).lower()
        return str(key).replace("Key.","").lower()

    def start_recording(self):
        self.stop_all()
        self.actions=[]; self.recording=True; self.last_action_time=time.perf_counter()
        self.status.set("Recording… press Stop when finished")
        self.refresh()
        self.record_kb_listener=keyboard.Listener(on_press=self.record_press,on_release=self.record_release)
        self.record_mouse_listener=mouse.Listener(on_click=self.record_click,on_move=self.record_move)
        self.record_kb_listener.start(); self.record_mouse_listener.start()

    def rec_delay(self):
        now=time.perf_counter(); d=int((now-self.last_action_time)*1000); self.last_action_time=now
        return min(max(d,0),60000)

    def record_press(self,key):
        if not self.recording:return
        name=self.key_name(key)
        if name in self.record_held:return
        self.record_held.add(name)
        self.actions.append(Action("Key Down",name,self.rec_delay()))
        self.root.after(0,self.refresh)

    def record_release(self,key):
        if not self.recording:return
        name=self.key_name(key); self.record_held.discard(name)
        self.actions.append(Action("Key Up",name,self.rec_delay()))
        self.root.after(0,self.refresh)

    def record_click(self,x,y,button,pressed):
        if not self.recording:return
        name=str(button).replace("Button.","")
        self.actions.append(Action("Mouse Down" if pressed else "Mouse Up",name,self.rec_delay(),True,int(x),int(y)))
        self.root.after(0,self.refresh)

    def record_move(self,x,y):
        if not self.recording:return
        now=time.perf_counter()
        if now-self.last_action_time < 0.08:return
        self.actions.append(Action("Mouse Move",f"{int(x)},{int(y)}",self.rec_delay(),True,int(x),int(y)))
        self.root.after(0,self.refresh)

    def stop_all(self):
        self.recording=False; self.stop_event.set(); self.playing=False
        for l in (self.record_kb_listener,self.record_mouse_listener):
            if l:
                try:l.stop()
                except Exception:pass
        self.record_kb_listener=self.record_mouse_listener=None
        self.record_held.clear()
        self.status.set("Stopped / Ready")

    def add_key(self):
        s=simpledialog.askstring("Add key","Key name (e.g. space, w, e, f1):",parent=self.root)
        if s:self.actions.append(Action("Key Tap",s.strip().lower(),10));self.refresh()

    def add_click(self):
        s=simpledialog.askstring("Add click","Mouse button: left, right, or middle",initialvalue="left",parent=self.root)
        if s and s.lower() in ("left","right","middle"):
            self.actions.append(Action("Mouse Click",s.lower(),10));self.refresh()

    def add_wait(self):
        n=simpledialog.askinteger("Add wait","Wait duration in milliseconds:",initialvalue=100,minvalue=0,maxvalue=60000,parent=self.root)
        if n is not None:self.actions.append(Action("Wait","",n));self.refresh()

    def add_angle(self):
        try:
            ang=int(self.angle.get())%360; dist=max(1,int(self.distance.get())); dur=max(0,int(self.angle_duration.get()))
        except Exception:
            messagebox.showerror("Invalid movement","Use an angle from 0–360, a positive distance and a duration in milliseconds.");return
        rad=math.radians(ang); dx=round(math.cos(rad)*dist); dy=round(math.sin(rad)*dist)
        detail=f"angle={ang}°, distance={dist}px"
        self.actions.append(Action("Mouse Relative",detail,10,True,dx,dy,dur));self.refresh()

    def toggle_action(self):
        i=self.selected()
        if i is not None:self.actions[i].enabled=not self.actions[i].enabled;self.refresh()

    def edit_delay(self):
        i=self.selected()
        if i is None:return
        n=simpledialog.askinteger("Edit delay","Delay before this action (ms):",initialvalue=self.actions[i].delay_ms,minvalue=0,maxvalue=60000,parent=self.root)
        if n is not None:self.actions[i].delay_ms=n;self.refresh()

    def edit_duration(self):
        i=self.selected()
        if i is None:return
        a=self.actions[i]
        if a.kind!="Mouse Relative":
            messagebox.showinfo("Move time","Select a Mouse Relative angle movement first.");return
        n=simpledialog.askinteger("Edit move time","How long should this angle movement take (ms)?",initialvalue=a.duration_ms,minvalue=0,maxvalue=60000,parent=self.root)
        if n is not None:a.duration_ms=n;self.refresh()

    def edit_value(self,event=None):
        i=self.selected()
        if i is None:return
        a=self.actions[i]
        v=simpledialog.askstring("Edit action","New action value:",initialvalue=a.value,parent=self.root)
        if v is not None:a.value=v.strip();self.refresh()

    def move(self,d):
        i=self.selected()
        if i is None:return
        j=i+d
        if 0<=j<len(self.actions):
            self.actions[i],self.actions[j]=self.actions[j],self.actions[i];self.refresh();self.tree.selection_set(str(j))

    def delete_action(self):
        i=self.selected()
        if i is not None:del self.actions[i];self.refresh()

    def clear(self):
        if messagebox.askyesno("Clear actions","Delete all actions?"):self.actions=[];self.refresh()

    def play(self):
        if self.playing:return
        if not self.actions:
            messagebox.showinfo("No actions","Record or add actions first.");return
        try:reps=max(1,int(self.repeat_count.get()))
        except ValueError:messagebox.showerror("Repeat count","Enter a positive whole number.");return
        self.stop_event.clear();self.playing=True
        self.status.set("Waiting for trigger…" if self.trigger_key.get()!="None" else "Playing…")
        threading.Thread(target=self.worker,args=(reps,),daemon=True).start()

    def worker(self,reps):
        trigger=self.trigger_key.get().strip().lower()
        if trigger!="none":
            while not self.stop_event.is_set():
                if trigger in self.pressed_now:break
                time.sleep(.003)
        if self.stop_event.wait(max(0,int(self.start_delay.get()))/1000):
            self.playing=False;return
        count=0
        loops=999999999 if self.loop.get() or self.run_mode.get()=="While key is held" else reps
        try:
            for _ in range(loops):
                if self.stop_event.is_set():break
                if self.run_mode.get()=="While key is held" and self.hold_key.get().strip().lower() not in self.pressed_now:break
                actions=list(self.actions); limit=max(0,int(self.action_limit.get()))
                for a in actions:
                    if self.stop_event.is_set():break
                    if self.run_mode.get()=="While key is held" and self.hold_key.get().strip().lower() not in self.pressed_now:break
                    if not a.enabled:continue
                    delay=max(0,a.delay_ms)/1000/max(.05,float(self.speed.get()))
                    if delay and self.stop_event.wait(delay):break
                    self.execute(a);count+=1
                    if limit and count>=limit:self.stop_event.set();break
                if self.stop_event.is_set():break
                if self.stop_event.wait(max(0,int(self.repeat_interval.get()))/1000/max(.05,float(self.speed.get()))):break
        except Exception as e:
            self.root.after(0,lambda err=str(e):messagebox.showerror("Playback error",err))
        self.playing=False
        self.root.after(0,lambda:self.status.set("Stopped / Ready"))

    def execute(self,a):
        if a.kind in ("Key Down","Key Up","Key Tap"):
            k=self.parse_key(a.value)
            if a.kind=="Key Down":self.kb.press(k)
            elif a.kind=="Key Up":self.kb.release(k)
            else:self.kb.press(k);self.kb.release(k)
        elif a.kind in ("Mouse Down","Mouse Up","Mouse Click"):
            b={"left":mouse.Button.left,"right":mouse.Button.right,"middle":mouse.Button.middle}.get(a.value.lower(),mouse.Button.left)
            if a.kind=="Mouse Down":self.ms.press(b)
            elif a.kind=="Mouse Up":self.ms.release(b)
            else:self.ms.press(b);self.ms.release(b)
        elif a.kind=="Mouse Move" and a.x is not None and a.y is not None:
            self.ms.position=(a.x,a.y)
        elif a.kind=="Mouse Relative" and a.x is not None and a.y is not None:
            dx,dy=a.x,a.y; duration=max(0,a.duration_ms)/1000/max(.05,float(self.speed.get()))
            if duration<=0:
                x,y=self.ms.position;self.ms.position=(x+dx,y+dy);return
            # Smoothly spread movement over the requested duration, while remaining interruptible.
            steps=max(1,min(240,int(duration/.008)))
            sx,sy=self.ms.position
            start=time.perf_counter()
            for n in range(1,steps+1):
                if self.stop_event.is_set():break
                frac=n/steps
                self.ms.position=(sx+round(dx*frac),sy+round(dy*frac))
                target=start+duration*frac
                wait=target-time.perf_counter()
                if wait>0 and self.stop_event.wait(wait):break
        elif a.kind=="Wait":
            self.stop_event.wait(max(0,a.delay_ms)/1000/max(.05,float(self.speed.get())))

    def parse_key(self,name):
        name=name.strip().lower()
        aliases={"space":Key.space,"enter":Key.enter,"tab":Key.tab,"shift":Key.shift,"ctrl":Key.ctrl,"alt":Key.alt,"esc":Key.esc,"escape":Key.esc,"backspace":Key.backspace,"delete":Key.delete,"up":Key.up,"down":Key.down,"left":Key.left,"right":Key.right}
        if name in aliases:return aliases[name]
        if name.startswith("f") and name[1:].isdigit():return getattr(Key,name,Key.f6)
        return KeyCode.from_char(name[0])

    def _start_global_listener(self):
        def on_press(key):
            name=self.key_name(key);self.pressed_now.add(name)
            if name==self.emergency_hotkey.get().strip().lower():
                self.root.after(0,self.stop_all);return
            if name==self.stop_hotkey.get().strip().lower():
                self.root.after(0,self.stop_all);return
            if self.run_mode.get()=="While key is held" and name==self.hold_key.get().strip().lower():
                if not self.playing:self.root.after(0,self.play)
            elif name==self.start_hotkey.get().strip().lower() and self.run_mode.get()!="While key is held":
                self.root.after(0,self.play)
        def on_release(key):
            name=self.key_name(key);self.pressed_now.discard(name)
            if self.run_mode.get()=="While key is held" and name==self.hold_key.get().strip().lower():
                self.stop_event.set()
        self.global_listener=keyboard.Listener(on_press=on_press,on_release=on_release)
        self.global_listener.daemon=True;self.global_listener.start()

    def save(self):
        p=filedialog.asksaveasfilename(defaultextension=".json",filetypes=[("SwiftMacro profile","*.json")])
        if not p:return
        try:
            with open(p,"w",encoding="utf-8") as f:json.dump([asdict(a) for a in self.actions],f,indent=2)
            self.status.set("Profile saved")
        except Exception as e:messagebox.showerror("Save failed",str(e))

    def load(self):
        p=filedialog.askopenfilename(filetypes=[("SwiftMacro profile","*.json")])
        if not p:return
        try:
            with open(p,encoding="utf-8") as f:data=json.load(f)
            self.actions=[Action(**x) for x in data];self.refresh();self.status.set("Profile loaded")
        except Exception as e:messagebox.showerror("Load failed",str(e))

    def close(self):
        self.stop_all()
        if self.global_listener:
            try:self.global_listener.stop()
            except Exception:pass
        self.root.destroy()

if __name__=="__main__":
    root=tk.Tk()
    app=SwiftMacroPro(root)
    root.mainloop()

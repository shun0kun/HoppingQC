from forceplate import ForcePlateData
import scipy.signal
import numpy as np
import tkinter as tk
from tkinter import filedialog
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from pathlib import Path
import tempfile

MINIMUM_REQUIRED_HOPS_NUM = 15
MEASURED_HOPS_NUM = 5

def is_utf8(filepath: str | Path) -> bool:
	try:
		with open(filepath, encoding="utf-8") as f:
			f.read()
			return True
	except UnicodeDecodeError:
		return False

def show_error(msg: str) -> None:
	result_text.config(state="normal")
	result_text.delete("1.0", tk.END)
	result_text.insert(tk.END, f"Error: {msg}\n", "red")
	result_text.config(state="disabled")

def show_graph(time: list[float], vgrf: list[float], hops: list[tuple[int, int]]):
	ax.clear()
	ax.plot(time, vgrf, color="black", linewidth=1)
	if len(hops) >= MINIMUM_REQUIRED_HOPS_NUM:
		ax.plot(time[hops[4][0]:hops[4+MEASURED_HOPS_NUM-1][1]+1], vgrf[hops[4][0]:hops[4+MEASURED_HOPS_NUM-1][1]+1], color="red", linewidth=1)
	ax.tick_params(axis="both", direction="in",length=2, right=False, top=False, left=True, bottom=True, labelbottom=False, labelleft=False)
	ax.set_ylim(bottom=-100)
	ax.set_yticks(np.arange(0, max(vgrf) + 500, 500))
	ax.set_xlim(left=-0.5)
	ax.set_xticks(np.arange(0, max(time) + 1, 1))
	ax.set_position([0, 0, 1, 1])
	canvas.get_tk_widget().place(x=159, y=265, width=513, height=125)
	canvas.draw_idle()

def preprocess_vgrf(vgrf_raw: list[float]) -> list[float]:
	# Low-pass filtering
	filter_settings = scipy.signal.butter(
		2,					# order
		25.0,				# cutoff frequency [Hz]
		btype="lowpass",	# filter type
		fs=1000.0,			# sampling rate [Hz]
		output="sos"		# よくわからん
	)
	vgrf_proc = scipy.signal.sosfiltfilt(filter_settings, vgrf_raw).tolist()

	# Thresholding
	THRESHOLD =  10
	vgrf_proc = [x if x >= 10.0 else 0.0 for x in vgrf_proc]

	# 残った不正の山を除去する。bw以上かどうか判定。
	is_contact = vgrf_proc[0] > 0.0
	BW = 40 * 9.81 # 仮の値
	left = None
	for i in range(len(vgrf_proc)):
		if is_contact and vgrf_proc[i] == 0.0:
			is_contact = False
			if left is not None:
				right = i - 1
				if max(vgrf_proc[left:right+1]) < BW:
					vgrf_proc[left:right+1] = [0.0] * (right - left + 1)
		elif not is_contact and vgrf_proc[i] > 0.0:
			is_contact = True
			left = i

	return vgrf_proc

def extract_hops(vgrf: list[float]) -> list[tuple[int, int]]:
	hops = []
	is_contact = vgrf[0] > 0.0
	left_idx = None
	for i in range(len(vgrf)):
		if is_contact and vgrf[i] == 0.0:
			is_contact = False
		elif not is_contact and vgrf[i] > 0.0:
			is_contact = True
			right_idx = i
			if left_idx is not None:
				hops.append((left_idx, right_idx))
			left_idx = i
	return hops

def analyze():
	canvas.get_tk_widget().place_forget()
	result_text.config(state="normal")
	result_text.delete("1.0", tk.END)
	result_text.insert(tk.END, "Processing...\n")
	result_text.config(state="disabled")

	# ファイル処理
	filepath = path_entry.get().strip()
	path = Path(filepath)
	if not path.is_file():
		show_error("File not found.")
		return
	if path.suffix.lower() != ".csv":
		show_error("File must be a CSV file.")
		return
	try:
		if not is_utf8(path):
			with tempfile.TemporaryDirectory() as tmpdir:
				tmpfilepath = Path(tmpdir) / "converted.csv"
				with open(filepath, encoding="cp932") as f:
					content = f.read()
				with open(tmpfilepath, "w", encoding="utf-8") as f:
					f.write(content)
				fp = ForcePlateData(str(tmpfilepath))
				time = fp.get("時刻")
				vgrf_raw = fp.get("合成-Fz")
		else:
			fp = ForcePlateData(filepath)
			time = fp.get("時刻")
			vgrf_raw = fp.get("合成-Fz")
		if time is None or vgrf_raw is None:
			raise ValueError
		if len(time) == 0 or len(time) != len(vgrf_raw):
			raise ValueError
	except PermissionError:
		show_error("Permission denied.")
		return
	except OSError:
		show_error("Unable to read file.")
		return
	except (UnicodeError, ValueError, TypeError):
		show_error("Invalid CSV format.")
		return

	# Target frequency処理
	try:
		target_freq = float(freq_entry.get())
	except ValueError:
		show_error("Target frequency must be a positive number.")
		return
	if not np.isfinite(target_freq) or target_freq <= 0.0:
		show_error("Target frequency must be a positive number.")
		return

	# Tolerance処置
	try:
		tolerance = float(tolerance_entry.get())
	except ValueError:
		show_error("Tolerance must be a non-negative number.")
		return
	if not np.isfinite(tolerance) or tolerance < 0.0:
		show_error("Tolerance must be a non-negative number.")
		return

	# 解析
	vgrf_proc = preprocess_vgrf(vgrf_raw)
	hops = extract_hops(vgrf_proc)
	num_hops = len(hops)

	result_text.config(state="normal")
	result_text.delete("1.0", tk.END)
	result_text.insert(tk.END, f"Number of hops\t\t\t: {num_hops}\n")
	if num_hops >= MINIMUM_REQUIRED_HOPS_NUM:
		freq_list = [0.0] * MEASURED_HOPS_NUM
		for i in range(MEASURED_HOPS_NUM):
			freq_list[i] = 1 / (time[hops[i+4][1]] - time[hops[i+4][0]])
		measured_freq = np.mean(freq_list)
		percent_diff = (abs(measured_freq - target_freq) / target_freq) * 100.0
		result_text.insert(tk.END, f"Target frequency (Hz)\t\t\t: {target_freq}\n")
		result_text.insert(tk.END, f"Measured frequency (Hz)\t: {measured_freq:.3g}\n")
		result_text.insert(tk.END, f"Percent difference (%)\t\t: {percent_diff:.3g}")
		if percent_diff <= tolerance:
			result_text.insert(tk.END, f" <= {tolerance}\n",)
			result_text.insert(tk.END, "OK\n", "green")
		else:
			result_text.insert(tk.END, f" > {tolerance}\n")
			result_text.insert(tk.END, "KO\n", "red")
		show_graph(time, vgrf_proc, hops)
	else:
		result_text.insert(tk.END, f"At least {MINIMUM_REQUIRED_HOPS_NUM} hops are required.\nKO\n", "red")

	result_text.config(state="disabled")

	return 0

def browse_file():
	path = filedialog.askopenfilename()
	if path:
		path_entry.delete(0, tk.END)
		path_entry.insert(0, path)
	

if __name__ == "__main__":
	root = tk.Tk()
	root.title("Hopping Quality Checker")
	root.geometry("700x400")
	root.resizable(False, False)

	path_label = tk.Label(root, text="CSV file path").place(x=10, y=10)
	path_entry = tk.Entry(root)
	path_entry.place(x=155, y=10, width=435, height=28)
	browse_botton = tk.Button(root, text="Browse...", command=browse_file)
	browse_botton.place(x=600, y=8, width=78, height=28)

	freq_label = tk.Label(root, text="Target frequency (Hz)").place(x=10, y=50)
	freq_entry = tk.Entry(root)
	freq_entry.place(x=155, y=50, width=80, height=28)

	tolerance_label = tk.Label(root, text="Tolerance (%)").place(x=10, y=90)
	tolerance_entry = tk.Entry(root)
	tolerance_entry.place(x=155, y=90, width=80, height=28)	
	
	run_botton = tk.Button(root, text="Run", command=analyze)
	run_botton.place(x=10, y=130, width=60, height=28)

	result_label = tk.Label(root, text="Result").place(x=10, y=175)
	result_text = tk.Text(root, state="disabled")
	result_text.place(x=155, y=175, width=520, height=84)
	result_text.tag_configure("green", foreground="#00FF00")
	result_text.tag_configure("red", foreground="#FF0000")

	fig = Figure(figsize=(5.13, 1.25), dpi=100)
	ax = fig.add_subplot(111)
	canvas = FigureCanvasTkAgg(fig, master=root)
	root.mainloop()

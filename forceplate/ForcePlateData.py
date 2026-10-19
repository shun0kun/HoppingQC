import csv

class ForcePlateData:
	def __init__(self, filepath: str):
		self.fields = {
			"時刻": self._read_column(filepath, 0, 13),
			"右-Fz": self._read_column(filepath, 3, 13),
			"左-Fz": self._read_column(filepath, 13, 13),
			"合成-Fz": self._read_column(filepath, 23, 13),
			"右-速度計": [v / 3.6 for v in self._read_column(filepath, 29, 13)],	
			"左-速度計": [v / 3.6 for v in self._read_column(filepath, 30, 13)],
			"右-速度": [v / 3.6 for v in self._read_column(filepath, 31, 13)],
			"左-速度": [v / 3.6 for v in self._read_column(filepath, 32, 13)]
		}

	@staticmethod
	def _read_column(filepath: str, col: int, start_row: int = 0) -> list[float]:
		arr = []
		with open(filepath, encoding="utf-8-sig", newline="") as f:
			reader = csv.reader(f)
			for i, row in enumerate(reader):
				if i < start_row:
					continue
				arr.append(float(row[col]))
		return arr

	def get(self, field: str) -> list[float]:
		return self.fields[field]

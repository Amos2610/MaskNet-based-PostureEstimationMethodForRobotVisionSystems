import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset
from torch.utils.data import DataLoader
import h5py
import subprocess
import shlex
import json
import glob
from sklearn.neighbors import NearestNeighbors
from scipy.spatial.distance import minkowski
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation
from torch import sin, cos
import open3d as o3d
from tqdm import tqdm
import torchvision
import logging
import random
import Registration_test_jurai
import time

# モデルのロード
save_path = "/home/nishidalab0/MaskNet/checkpoint/model_weight_epoch300_batchsize32_plane.pth"
model_load = torch.load(save_path)

# テンプレートデータのロード
#pcd_file = "/home/nishidalab0/MaskNet/TNUTEJN016.pcd"
pcd_file = "/home/nishidalab0/MaskNet/TNUTEJN016_half2.pcd"

# ソースデータのロード
if Registration_test_jurai.theta == 0:   ## 0度 ##
	pcd_rot_file = "/home/nishidalab0/MaskNet/sensor_cheese_noise.pcd"
elif Registration_test_jurai.theta == 45:   ## 45度 ##
	pass
	pcd_rot_file = "/home/nishidalab0/MaskNet/sensor_tpip_45_3.pcd"
elif Registration_test_jurai.theta == 90:   ## 90度 ##
	pcd_rot_file = "/home/nishidalab0/MaskNet/sensor_tpip_90_1.pcd"
elif Registration_test_jurai.theta == 135:   ## 135度 ##
	pass
	pcd_rot_file = "/home/nishidalab0/MaskNet/sensor_tpip_135_2.pcd"
elif Registration_test_jurai.theta == "L_90":   ## L90 ##
	pcd_rot_file = "/home/nishidalab0/MaskNet/sensor_Ljoint_90_4.pcd"
	pcd_file = "/home/nishidalab0/MaskNet/WMU2LR2020_half2.pcd"
elif Registration_test_jurai.theta == "L_180":   ## L180 ##
	pcd_rot_file = "/home/nishidalab0/MaskNet/sensor_Ljoint_180_2.pcd"
	pcd_file = "/home/nishidalab0/MaskNet/WMU2LR2020_half2.pcd"

# テンプレとソースを点群データに変換
pcd_cheese = o3d.io.read_point_cloud(pcd_file)
pcd_cheese_rot = o3d.io.read_point_cloud(pcd_rot_file)

numpy_cheese_points = np.array(pcd_cheese.points)
numpy_cheese_rot_points = np.array(pcd_cheese_rot.points)

###print("テンプレートの点群数：", np.shape(numpy_cheese_points))
###print("ソースの点群数：", np.shape(numpy_cheese_rot_points))

numpy_cheese_points = np.array(pcd_cheese.points)
numpy_cheese_rot_points = np.array(pcd_cheese_rot.points)

pcd_cheese_points = o3d.geometry.PointCloud()
pcd_cheese_points.points = o3d.utility.Vector3dVector(numpy_cheese_points)
pcd_cheese_rot_points = o3d.geometry.PointCloud()
pcd_cheese_rot_points.points = o3d.utility.Vector3dVector(numpy_cheese_rot_points)

pcd_cheese_points.paint_uniform_color([1.0, 0, 0])
pcd_cheese_rot_points.paint_uniform_color([0, 1.0, 0])

# テンプレート点群とソース点群の表示
###o3d.visualization.draw_geometries([pcd_cheese_points, pcd_cheese_rot_points])

device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
model_load.to(device)

template_cheese = torch.tensor(numpy_cheese_points, dtype=torch.float32).unsqueeze(0)
source_cheese = torch.tensor(numpy_cheese_rot_points, dtype=torch.float32).unsqueeze(0)
template_cheese = template_cheese.to(device)
source_cheese = source_cheese.to(device)

# 位置合わせ準備を行う（関数を呼び出す）、定義するだけ
registration_model = Registration_test_jurai.Registration()

start = torch.cuda.Event(enable_timing=True)
end = torch.cuda.Event(enable_timing=True)

#####計測開始#####
start.record()

# ※template_cheese、source_cheeseはtensor型
###print("\nテンプレ点群の配列のサイズ：", template_cheese.size())
###print("ソース点群の配列のサイズ：", source_cheese.size(), "\n")

counter = 1
n = 1
sum_diff_R = 0
sum_diff_t = 0
lists_R = []
lists_t = []
while counter <= n:
	# 従来手法（RANSAC、ICP）の実行（実際のデータを代入）
	result_cheese = registration_model.register(template_cheese, source_cheese)
	est_T_cheese = result_cheese['est_T']     # est_T：RANSAC+ICPの変換行列

	# RANSAC+ICP処理、点群の表示
	Registration_test_jurai.display_results_sample(
		template_cheese.detach().cpu().numpy()[0], 
		source_cheese.detach().cpu().numpy()[0], 
		est_T_cheese.detach().cpu().numpy()[0], 
		template_cheese.detach().cpu().numpy()[0])
	
	sum_diff_R += Registration_test_jurai.diff_R
	sum_diff_t += Registration_test_jurai.diff_t
	
	lists_R.append(Registration_test_jurai.diff_R)
	lists_t.append(Registration_test_jurai.diff_t)
	
	counter += 1
# 平均
mean_diff_R = sum_diff_R / n
mean_diff_t = sum_diff_t / n
print("\n回転行列のL2ノルムの平均：", mean_diff_R)
print("平行移動ベクトルのL2ノルムの平均：", mean_diff_t)
# 分散
dev_diff_R = 0
dev_diff_t = 0
for i in range(n):
	dev_diff_R += (lists_R[i] - mean_diff_R)**2
	dev_diff_t += (lists_t[i] - mean_diff_t)**2
var_diff_R = dev_diff_R / n
var_diff_t = dev_diff_t / n
print("\n回転行列のL2ノルムの分散：", var_diff_R)
print("平行移動ベクトルのL2ノルムの分散：", var_diff_t)

#print(len(source_cheese.detach().cpu().numpy()[0]))
#print(len(masked_template_cheese.detach().cpu().numpy()[0]))

#####計測終了#####
end.record()
torch.cuda.synchronize()
elapsed_time = start.elapsed_time(end)
#print(elapsed_time / 1000, 'sec.')

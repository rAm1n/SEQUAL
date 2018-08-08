


import json
from scipy.misc import imread
from PIL import Image
import numpy as np
import zipfile
import tarfile
import os
import requests
import wget
import ssl




ssl._create_default_https_context = ssl._create_unverified_context

CONFIG = {
	'data_path' : os.path.expanduser('~/tmp/saliency/'),
	'dataset_json' : os.path.join(os.path.dirname(__file__), 'data/dataset.json'),
	'auto_download' : True,
}


DATASETS = ['TORONTO', 'CAT2000', 'CROWD', 'SALICON', 'LOWRES',\
		 'KTH', 'OSIE', 'MIT1003', 'PASCAL']


class SaliencyDataset(object):
	def __init__(self, config=CONFIG):
		self.name = None
		self.config = config

	def __repr__(self):
		return 'Dataset object - {0}'.format(self.name)

	def __str__(self):
		return 'Dataset object - {0}'.format(self.name)

	def __len__(self):
		if self.name:
			return len(self.data)
		else:
			print('dataset has not been loaded yet.')
			return 0

	def load(self, name):
		name = name.upper()
		if name not in DATASETS:
			print('{0} has not been converted yet.'.format(name))
			return False
		self._load_json(name)


	def dataset_names(self):
		return DATASETS

	def _load_json(self, name):
		try:
			dataset_file = self.config['dataset_json']
			with open(dataset_file, 'r') as f_handle:
				data = json.load(f_handle)[name]
				for key, value in data.items():
					if not hasattr(SaliencyDataset, key):
						self.__setattr__(key, np.array(value))
						if key == 'data_type':
							for d_type in value:
								self.__setattr__(d_type, None)
			self.name = name

		except KeyError:
			print('{0} has not been converted yet'.format(self.name))

		except Exception as x:
			print(x)
			print('something went wrong')
			exit()

		try:
			self.directory = os.path.join(self.config['data_path'], self.name)
			if not os.path.isdir(self.directory):
					os.makedirs(self.directory)
		except OSError as e:
				raise e

	def _download(self, url, path, key, extract=False):

		try:
			print('downloading - {0}'.format(url))
			def save_response_content(response, destination):
				CHUNK_SIZE = 32768
				try:
					with open(destination, "wb") as f:
						for chunk in response.iter_content(CHUNK_SIZE):
							if chunk: # filter out keep-alive new chunks
								f.write(chunk)
				except Exception as x:
					print(x)
			if ("drive.google.com" in url):
				def get_confirm_token(response):
					for key, value in response.cookies.items():
						if key.startswith('download_warning'):
							return value
					return None
				filename = url.split('=')[-1] + '.zip'
				file_extension = 'zip'
				destination = os.path.join(self.config['data_path'], self.name, filename)

				session = requests.Session()
				response = session.get(url, stream = True)
				token = get_confirm_token(response)

				if token:
					params = { 'confirm' : token }
					response = session.get(url, params = params, stream = True)

				save_response_content(response, destination)
			else:
				filename = url.split('/')[-1]
				file_extension = filename.split('.')[-1]
				#destination = os.path.join(path, filename)
				destination =  os.path.join(path, key + '.' + file_extension)
				print(destination)
				if 'dropbox' in url:
					url += '?dl=1'
				wget.download(url, destination)

			if file_extension == 'zip':
				zip_ref = zipfile.ZipFile(destination, 'r')
				zip_ref.extractall(path)
				zip_ref.close()
				os.remove(destination)
			elif file_extension == 'tgz':
				tar = tarfile.open(destination, 'r')
				tar.extractall(path)
				tar.close()
				os.remove(destination)

		except Exception as x:
			print(x)
			os.rmdir(path)


	def _load(self, key):
		try:
			sub_dir = os.path.join(self.directory, key)
			if not os.path.isdir(sub_dir): # download
				try:
					os.makedirs(sub_dir)
					self._download(self.url.item()[key], sub_dir, key)
				except Exception as x:
					print(x)

			if ('sequence' in key) and ( getattr(self, key) is None):
				npz_file = os.path.join(sub_dir, '{0}.npz'.format(key))
				with open(npz_file, 'rb') as f_handle:
					self.__setattr__(key, np.load(f_handle, encoding='latin1'))
			else:
				pass
				# to be implemented.

		except Exception as x:
			print(x)

	def get(self, data_type, **kargs):
		result = list()
		# loading required data
		if data_type in ['sequence', 'fixation', 'fixation_time']:
			self._load('sequence')
		elif data_type in ['sequence_mouse_lab', 'sequence_mouse_amt']:
			self._load(data_type)
	
		elif data_type in ['heatmap', 'heatmap_path']:
			if 'heatmap' not in self.url.item():  # heatmaps in main package.
				self._load('data')
			else: 								  # seperate url for heatmaps.
				self._load('heatmap')
		elif data_type in ['stimuli', 'stimuli_path']:
			self._load('data')

		if 'index' in kargs:
			index = kargs['index']
		else:
			index = range(len(self.data))

		for idx, img in enumerate(self.data[index]):
			if 'sequence' in data_type:
				tmp = list()
				for user in getattr(self, data_type)[idx]:
					user = np.array(user)
					if 'percentile' in kargs:
						if kargs['percentile']:
							if(user.shape)[0] == 0:
								continue
							_sample = user[:,:2] / self.img_size
							user = np.concatenate((_sample, user[:,2:]), axis=1)
					if 'modify' in kargs:
						if kargs['modify']== 'fix' :
							if 'percentile' in kargs:
								if kargs['percentile']:
									mask_greater = _sample > 1.0
									mask_smaller = _sample < 0.0
									_sample[mask_greater] = (1.0 - np.finfo(float).eps)
									_sample[mask_smaller] = np.finfo(float).eps
									user = np.concatenate((_sample, user[:,2:]), axis=1)
							else:
									# TODO
								print('fix was ignored, only works in percentile mode.')
						elif kargs['modify'] == 'remove':
							if 'percentile' in kargs:
								if kargs['percentile']:
									user = user[user[:,0]<=(1 - np.finfo(float).eps), :]
									user = user[user[:,0]>=(np.finfo(float).eps), :]
									user = user[user[:,1]<=(1-np.finfo(float).eps), :]
									user = user[user[:,1]>=(np.finfo(float).eps), :]
							else:
								w , h = self.img_size
								user = user[user[:,0]<=(w - np.finfo(float).eps), :]
								user = user[user[:,0]>=(np.finfo(float).eps), :]
								user = user[user[:,1]<=(h-np.finfo(float).eps), :]
								user = user[user[:,1]>=(np.finfo(float).eps), :]
					tmp.append(user)
				tmp = np.array(tmp)

			elif data_type =='heatmap':
				path = os.path.join(self.directory, img['heatmap'])
				if os.path.isfile(path):
					tmp = imread(path)

			elif data_type == 'heatmap_path':
				tmp = os.path.join(self.directory, img['heatmap'])

			elif data_type =='stimuli':
				path = os.path.join(self.directory, img['stimuli'])
				if os.path.isfile(path):
					tmp = imread(path)
					if tmp.ndim != 3:
						shape = tmp.shape
						tmp = np.array(Image.fromarray(tmp).convert('RGB').getdata()).reshape(shape + (3,))
			elif data_type == 'stimuli_path':
				tmp = os.path.join(self.directory, img['stimuli'])
			elif data_type == 'fixation':
				h, w = img['img_size']
				tmp = np.zeros((h,w))
				for user in self.sequence[idx]:
					for fix in user:
						if (fix[1] < h) and (fix[0] < w):
							tmp[int(fix[1]), int(fix[0])] = 1
			elif data_type == 'fixation_time':
				h , w = img['img_size']
				user_count = len(self.sequence[idx])
				tmp = np.zeros((user_count, h, w), dtype=np.float32)
				for user_idx, user in enumerate(self.sequence[idx]):
					for fix in user:
						if (fix[1] < h) and (fix[0] < w):
							tmp[user_idx, int(fix[1]), int(fix[0])] = fix[2]
				tmp[tmp == 0] = np.nan
				tmp = np.nanmean(tmp, axis=0)
				tmp[np.isnan(tmp)] = 0
			else:
				try:
					tmp = self.data[data_type]
				except Exception as x:
					return False
			result.append(tmp)


		#un-load data

		return np.asarray(result)

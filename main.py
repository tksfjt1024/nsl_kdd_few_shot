#!/usr/bin/env python3

#!/usr/bin/env python3

import plaidml.keras
import os
plaidml.keras.install_backend()
os.environ["KERAS_BACKEND"] = "plaidml.keras.backend"

from constants import CONFIG
from classifications import calc_ensemble_accuracy
from data_processing import data_processing
from callbacks import Histories
from models import build_fsl_cnn
from losses import center_loss
from keras.optimizers import Adam, SGD, RMSprop, Nadam
from keras.models import Model, model_from_json, load_model
from keras.layers import (
    Input
)
import numpy as np
from multiprocessing import Pool, cpu_count
from time import sleep


def train(args):
  index, x_train, x_support, x_test, y_train, y_support, y_test, y_train_value, y_support_value, y_test_value, input_shape = args
  sleep(index % cpu_count())
  print("Setting up Model " + str(index + 1) + "/" + str(CONFIG["num_models"]))

  input = Input(shape=input_shape)
  output = build_fsl_cnn(input)
  model = Model(inputs=input, outputs=output)
  model.compile(
      # optimizer=RMSprop(),
      #   optimizer=SGD(lr=0.0020),
    #   optimizer=Nadam(),
      optimizer=Adam(),
      loss=[
          center_loss(
              x_support,
              y_support,
              y_support_value,
              model
          )
      ],
  )

  expanded_y_train = np.array(
      [
          np.concatenate(
              [
                  y,
                  np.full(
                      CONFIG["output_dim"] - y_train.shape[1],
                      0.0,
                  )
              ]
          ) for y in y_train
      ]
  )

  histories = Histories(
      x_train,
      y_train_value,
      x_test,
      y_test_value,
      x_support,
      y_support_value,
      index
  )

  model.fit(
      x_train,
      expanded_y_train,
      batch_size=CONFIG["batch_size"] + index * 10,
      epochs=CONFIG["epochs"],
      verbose=False,
      callbacks=[
          histories
      ]
  )

  return x_support, y_support_value, index


def load_models(index):
  sleep(index % cpu_count())
  print("Load Model " + str(index + 1) + "/" + str(CONFIG["num_models"]))

  models = [
      load_model(
          "./temp/model_" + str(index) + "_epoch_" + str(j) + ".h5",
          compile=False
      )
      for j in range(CONFIG["epochs"])
  ]
  return models, index


def main():
  _, x_support, x_test, _, y_support, y_test, _, y_support_value, y_test_value, input_shape = data_processing()
  # x_train, x_support, x_test, y_train, y_support, y_test, y_train_value, y_support_value, y_test_value, input_shape = data_processing()
  #   p = Pool(cpu_count())
  p = Pool(CONFIG["num_models"])
  datasets = np.array(p.map(data_processing, range(CONFIG["num_models"])))
  args = []
  for i in range(CONFIG["num_models"]):
    _, x_train, _, _, y_train, _, _, y_train_value, _, _, _ = datasets[i]
    args.append(
      [
        i,
        x_train,
        x_support,
        x_test,
        y_train,
        y_support,
        y_test,
        y_train_value,
        y_support_value,
        y_test_value,
        input_shape
      ]
    )
  results = np.array(p.map(train, args))
  results = np.array(sorted(results, key=lambda x: x[-1]))

  print("-" * 200)

  models = np.array(p.map(load_models, range(CONFIG["num_models"])))
  models = np.array(sorted(models, key=lambda x: x[-1]))
  models = models[:, 0]
  # x_supports = results[:, 0]
  # y_supports = results[:, 1]

  calc_ensemble_accuracy(x_test, y_test_value, x_support, y_support_value, models)


if __name__ == "__main__":
  main()

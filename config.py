# encoding:utf-8

import copy
import json
import logging
import os
import pickle

from common.log import logger


class Config(dict):
    def __init__(self, d=None):
        super().__init__()
        if d is None:
            d = {}
        for k, v in d.items():
            self[k] = v
        # user_datas: 用户数据，key为用户名，value为用户数据，也是dict
        self.user_datas = {}

    def __getitem__(self, key):
        return super().__getitem__(key)

    def __setitem__(self, key, value):
        return super().__setitem__(key, value)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError as e:
            return default
        except Exception as e:
            raise e

    # Make sure to return a dictionary to ensure atomic
    def get_user_data(self, user) -> dict:
        if self.user_datas.get(user) is None:
            self.user_datas[user] = {}
        return self.user_datas[user]

    def load_user_datas(self):
        try:
            with open(os.path.join(get_appdata_dir(), "user_datas.pkl"), "rb") as f:
                self.user_datas = pickle.load(f)
                logger.info("[Config] User datas loaded.")
        except FileNotFoundError as e:
            logger.info("[Config] User datas file not found, ignore.")
        except Exception as e:
            logger.info("[Config] User datas error: {}".format(e))
            self.user_datas = {}

    def save_user_datas(self):
        try:
            with open(os.path.join(get_appdata_dir(), "user_datas.pkl"), "wb") as f:
                pickle.dump(self.user_datas, f)
                logger.info("[Config] User datas saved.")
        except Exception as e:
            logger.info("[Config] User datas error: {}".format(e))


config = Config()


def drag_sensitive(config):
    try:
        if isinstance(config, str):
            conf_dict: dict = json.loads(config)
            conf_dict_copy = copy.deepcopy(conf_dict)
            for key in conf_dict_copy:
                if "key" in key or "secret" in key:
                    if isinstance(conf_dict_copy[key], str):
                        conf_dict_copy[key] = (
                            conf_dict_copy[key][0:3]
                            + "*" * 5
                            + conf_dict_copy[key][-3:]
                        )
            return json.dumps(conf_dict_copy, indent=4)

        elif isinstance(config, dict):
            config_copy = copy.deepcopy(config)
            for key in config:
                if "key" in key or "secret" in key:
                    if isinstance(config_copy[key], str):
                        config_copy[key] = (
                            config_copy[key][0:3] + "*" * 5 + config_copy[key][-3:]
                        )
            return config_copy
    except Exception as e:
        logger.exception(e)
        return config
    return config


def load_config():
    global config
    config_path = "./config.json"
    if not os.path.exists(config_path):
        logger.info("配置文件不存在，将使用config-template.json模板")
        config_path = "./config-template.json"

    config_str = read_file(config_path)
    logger.debug("[INIT] config str: {}".format(drag_sensitive(config_str)))

    # 将json字符串反序列化为dict类型
    config = Config(json.loads(config_str))

    # override config with environment variables.
    # Some online deployment platforms (e.g. Railway) deploy project from github directly. So you shouldn't put your secrets like api key in a config file, instead use environment variables to override the default config.
    for name, value in os.environ.items():
        name = name.lower()
        logger.info(
            "[INIT] override config by environ args: {}={}".format(name, value)
        )
        try:
            config[name] = eval(value)
        except:
            if value == "false":
                config[name] = False
            elif value == "true":
                config[name] = True
            else:
                config[name] = value

    if config.get("debug", False):
        logger.setLevel(logging.DEBUG)
        logger.debug("[INIT] set log level to DEBUG")

    logger.info("[INIT] load config: {}".format(drag_sensitive(config)))

    config.load_user_datas()


def get_root():
    return os.path.dirname(os.path.abspath(__file__))


def read_file(path):
    with open(path, mode="r", encoding="utf-8") as f:
        return f.read()


def conf():
    return config


def get_appdata_dir():
    data_path = os.path.join(get_root(), conf().get("appdata_dir", ""))
    if not os.path.exists(data_path):
        logger.info("[INIT] data path not exists, create it: {}".format(data_path))
        os.makedirs(data_path)
    return data_path

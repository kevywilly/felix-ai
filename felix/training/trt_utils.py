# https://github.com/NVIDIA/TensorRT/blob/main/samples/python/yolov3_onnx/onnx_to_tensorrt.py

import torch
from torchvision.models.alexnet import alexnet
import tensorrt as trt
from felix.settings import settings
import os
from lib.log import logger

TRT_LOGGER = trt.Logger()

EXPLICIT_BATCH = 1 << (int)(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH)

class TRTUtils:
   
    def __init__(self, profile: TrainingProfile):
        self.profile = profile

    def onnx_model_exists(self) -> bool:
        return os.path.isfile(self.profile.onnx_file)
    
    def trt_model_exists(self) -> bool:
        return os.path.isfile(self.profile.trt_file)
    
    def torch2onnx(self, overwrite: bool = False):
        """ Converts a pytorch file to onnx """
        profile = self.profile

        if not overwrite and self.onnx_model_exists():
            msg = f"Onnx file {profile.onnx_file} already exists."
            logger.error(msg)
            raise Exception(msg)

        if not os.path.isfile(profile.best_model_file):
            msg = f"Best model file {profile.best_model_file} not found."
            logger.error(msg)
            raise Exception(msg)        

        logger.info("Loading alexnet")
        model = alexnet(pretrained=True).eval()

        logger.info(f"Loading torch model: {profile.best_model_file}")
        num_cats = len(profile.categories)

        logger.info(f"Configuring model for {num_cats} categories.")
        model.classifier[6] = torch.nn.Linear(model.classifier[6].in_features, num_cats)
        model.load_state_dict(torch.load(profile.best_model_file))

        logger.info("Sending model to gpu.")
        device = torch.device('cuda')
        model.to(device)

        logger.info(f"Converting and saving onnx file: {profile.onnx_file}")

        dummy_input = torch.ones((1, 3, 224, 224)).cuda()
        torch.onnx.export(
            model, 
            dummy_input, 
            profile.onnx_file, 
            export_params=True, 
            opset_version=10, 
            do_constant_folding=True,
            input_names = ['modelInput'], 
            output_names = ['modelOutput'], 
            dynamic_axes={'modelInput' : {0 : 'batch_size'},'modelOutput' : {0 : 'batch_size'}}) 
        
        logger.info("Sending model to gpu.")
        
    def onnx2trt(self, overwrite: bool = False):
        """Attempts to load a serialized engine if available, otherwise builds a new TensorRT engine and saves it."""
        
        if not overwrite and self.trt_model_exists():
            raise Exception("trt model already exists")

        if not self.onnx_model_exists():
            raise Exception("please build onnx model first.")
        
        profile = self.profile

        def build_engine():
            """Takes an ONNX file and creates a TensorRT engine to run inference with"""
        
            with trt.Builder(TRT_LOGGER) as builder, builder.create_network(
                EXPLICIT_BATCH
            ) as network, builder.create_builder_config() as config, trt.OnnxParser(
                network, TRT_LOGGER
            ) as parser, trt.Runtime(
                TRT_LOGGER
            ) as runtime:
                config.max_workspace_size = 1 << 28  # 256MiB
                builder.max_batch_size = 1
                # Parse model file
                if not os.path.exists(profile.onnx_file):
                    logger.info(
                        f"ONNX file {profile.onnx_file} not found, please run yolov3_to_onnx.py first to generate it."
                    )
                    exit(0)
                logger.info(f"Loading ONNX file from path {profile.onnx_file}...")
                with open(profile.onnx_file, "rb") as model:
                    logger.info("Beginning ONNX file parsing...")
                    if not parser.parse(model.read()):
                        logger.error("ERROR: Failed to parse the ONNX file.")
                        for error in range(parser.num_errors):
                            print(parser.get_error(error))
                        return None
                # The actual yolov3.onnx is generated with batch size 64. Reshape input to batch size 1
                network.get_input(0).shape = [1, 3, 224, 224]
                logger.info("Completed parsing of ONNX file")
                logger.info(f"Building an engine from file {profile.onnx_file}; this may take a while...")
                plan = builder.build_serialized_network(network, config)
                engine = runtime.deserialize_cuda_engine(plan)
                logger.info("Completed creating Engine.")
                with open(profile.trt_file, "wb") as f:
                    f.write(plan)
                return engine

        if os.path.exists(profile.trt_file):
            # If a serialized engine exists, use it instead of building an engine.
            logger.info("Reading engine from file {profile.trt_file}")
            with open(profile.trt_file, "rb") as f, trt.Runtime(TRT_LOGGER) as runtime:
                return runtime.deserialize_cuda_engine(f.read())
        else:
            return build_engine()
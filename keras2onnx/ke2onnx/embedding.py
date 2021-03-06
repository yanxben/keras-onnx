###############################################################################
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
###############################################################################
from ..common.onnx_ops import apply_reshape, apply_cast
from ..proto import onnx_proto

import numpy as np


def convert_keras_embed(scope, operator, container):
    op = operator.raw_operator  # Keras Embedding layer object
    if hasattr(op, 'mask_zero') and op.mask_zero == True:
        raise NotImplementedError("Embedding layer mask_zero attribute cannot be converted")

    # Reshape the indexes we want to embed to 1-D tensor. Otherwise, Gather's output may get wrong shape, which is the
    # same as our CoreML Embedding converter.
    reshaped_input_name = scope.get_unique_variable_name('embedding_reshaped')
    apply_reshape(scope, operator.inputs[0].full_name, reshaped_input_name, container, desired_shape=[0, -1])

    cast_name = scope.get_unique_variable_name('casted')
    apply_cast(scope, reshaped_input_name, cast_name, container, to=onnx_proto.TensorProto.INT32)

    # Prepare the weight matrix (i.e., the vectors of all input indices) as an initializer so that the following main
    # operator can access it.
    embedding_tensor_name = scope.get_unique_variable_name('W')
    weights = np.array(op.get_weights()[0].T).reshape(op.output_shape[-1], op.input_dim).transpose().flatten().tolist()
    container.add_initializer(embedding_tensor_name, onnx_proto.TensorProto.FLOAT,
                              [op.input_dim, op.output_shape[-1]], weights)

    # Create a Gather operator to extract the latent representation of each index
    op_type = 'Gather'
    attrs = {'name': operator.full_name}
    container.add_node(op_type, [embedding_tensor_name, cast_name], operator.output_full_names, **attrs)

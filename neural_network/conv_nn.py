import numpy as np


def sigmoid(x):
    return 1 / (1 + np.exp(-x))


def sigmoid_derivative(x):
    return x * (1 - x)


def relu(x):
    return np.maximum(0, x)


def relu_derivative(x):
    return (x > 0).astype(float)


def leaky_relu(x, alpha=0.01):
    return np.where(x > 0, x, alpha * x)


def leaky_relu_derivative(x, alpha=0.01):
    return np.where(x > 0, 1, alpha)


def stable_softmax(outputs):
    outputs -= np.max(outputs)
    exp_outputs = np.exp(outputs)
    return exp_outputs / np.sum(exp_outputs)


def pretty_print_prediction(outputs, target):
    print("[", end="")
    for output in outputs:
        print(f" {output:.5f}", end="")
    print(" ]", end="")
    print(" |", target)


class ConvLayer:
    def __init__(self, num_filters, input_depth, kernel_size, eta=0.01):
        self.num_filters = num_filters
        self.kernel_size = kernel_size
        self.eta = eta
        # init kernels randomly
        self.kernels = np.random.rand(
            num_filters, input_depth, kernel_size, kernel_size) - 0.5
        self.biases = np.random.rand(num_filters) - 0.5

    def forward(self, inputs):
        self.inputs = inputs
        self.outputs = np.zeros(
            (self.num_filters, inputs.shape[1] - self.kernel_size + 1, inputs.shape[2] - self.kernel_size + 1))
        for k in range(self.num_filters):
            output = np.zeros(
                (inputs.shape[1] - self.kernel_size + 1, inputs.shape[2] - self.kernel_size + 1))
            for d in range(inputs.shape[0]):
                output += self.convolve2d(inputs[d], self.kernels[k, d])
            output += self.biases[k]
            self.outputs[k] = leaky_relu(output)
        return self.outputs

    def convolve2d(self, input_plane, kernel):
        kernel_height, kernel_width = kernel.shape
        output_height = input_plane.shape[0] - kernel_height + 1
        output_width = input_plane.shape[1] - kernel_width + 1
        output = np.zeros((output_height, output_width))
        for i in range(output_height):
            for j in range(output_width):
                region = input_plane[i:i+kernel_height, j:j+kernel_width]
                output[i, j] = np.sum(region * kernel)
        return output

    def backward(self, grad_outputs):
        grad_inputs = np.zeros_like(self.inputs)
        grad_kernels = np.zeros_like(self.kernels)
        grad_biases = np.zeros_like(self.biases)

        for k in range(self.num_filters):
            # Apply sigmoid derivative
            grad_output = grad_outputs[k] * \
                leaky_relu_derivative(self.outputs[k])
            # Bias gradient is the sum of the gradients
            grad_biases[k] = np.sum(grad_output)
            for d in range(self.inputs.shape[0]):
                # Convolve grad_output with the input to calculate kernel gradient
                grad_kernels[k, d] = self.convolve2d(
                    self.inputs[d], grad_output)
                # Perform full convolution (flip kernel and convolve with grad_output)
                flipped_kernel = np.flip(self.kernels[k, d], axis=(0, 1))
                padded_grad_output = np.pad(
                    grad_output,
                    ((self.kernel_size - 1, self.kernel_size - 1),
                     (self.kernel_size - 1, self.kernel_size - 1)),
                    mode='constant'
                )
                grad_inputs[d] += self.convolve2d(
                    padded_grad_output, flipped_kernel)

        # Update weights and biases
        self.kernels -= self.eta * grad_kernels
        self.biases -= self.eta * grad_biases

        return grad_inputs


class Perceptron:
    def __init__(self, input_nbr, eta=0.01):
        self.eta = eta
        self.weights = np.random.rand(input_nbr) - 0.5
        self.bias = np.random.rand() - 0.5

    def predict(self, inputs):
        weighted_sum = np.dot(inputs, self.weights) + self.bias
        return leaky_relu(weighted_sum)

    def update_weights(self, inputs, delta):
        self.weights += self.eta * delta * inputs
        self.bias += self.eta * delta


class Layer:
    def __init__(self, nbr_neurons, input_size, eta=0.01):
        self.neurons = [Perceptron(input_size, eta)
                        for _ in range(nbr_neurons)]
        self.outputs = np.zeros(nbr_neurons)

    def forward(self, inputs):
        self.inputs = inputs
        self.outputs = np.array([neuron.predict(inputs)
                                for neuron in self.neurons])
        return self.outputs

    def backward(self, inputs, deltas):
        new_deltas = np.zeros(len(inputs))
        for i, neuron in enumerate(self.neurons):
            delta = deltas[i] * leaky_relu_derivative(self.outputs[i])
            neuron.update_weights(inputs, delta)
            new_deltas += delta * neuron.weights
        return new_deltas


class NeuralNetwork:
    def __init__(self, input_shape, conv_layers, fully_connected, eta=0.01, epoch=1):
        # for now the four output are hard coded.
        # it is possible to let the user choose but idk if it is logic
        self.conv_layers = [ConvLayer(**params) for params in conv_layers]
        self.fc_layers = [
            Layer(size, prev_size, eta)
            for size, prev_size in zip(fully_connected[1:], fully_connected[:-1])
        ]
        self.output_layer = Layer(4, fully_connected[-1], eta)
        self.epoch = epoch

    def forward(self, inputs):
        for layer in self.conv_layers:
            inputs = layer.forward(inputs)
        inputs = inputs.flatten()
        for layer in self.fc_layers:
            inputs = layer.forward(inputs)
        outputs = self.output_layer.forward(inputs)
        outputs = stable_softmax(outputs)
        return outputs

    def train(self, inputs, target):
        outputs = self.forward(inputs)
        pretty_print_prediction(outputs, target)
        loss = -np.sum(target * np.log(outputs))
        grad_outputs = outputs - target
        grad_inputs = self.output_layer.backward(
            self.fc_layers[-1].outputs, grad_outputs)
        for i in range(len(self.fc_layers) - 1, 0, -1):
            grad_inputs = self.fc_layers[i].backward(
                self.fc_layers[i - 1].outputs, grad_inputs)
        grad_inputs = self.fc_layers[0].backward(inputs.flatten(), grad_inputs)
        for layer in reversed(self.conv_layers):
            grad_inputs = layer.backward(
                grad_inputs.reshape(layer.outputs.shape))
        return loss


# Example of usage
if __name__ == '__main__':
    input_shape = (16, 8, 8)
    conv_layers = [
        {"num_filters": 32, "input_depth": 16, "kernel_size": 3, "eta": 0.01},
        {"num_filters": 64, "input_depth": 32, "kernel_size": 3, "eta": 0.01},
    ]
    fully_connected = [1024, 512]

    nn = NeuralNetwork(input_shape, conv_layers, fully_connected, eta=0.001)

    dataset = [
        (np.random.rand(16, 8, 8), [1, 0, 0, 0]),  # Checkmate
        (np.random.rand(16, 8, 8), [0, 1, 0, 0]),  # Check
        (np.random.rand(16, 8, 8), [0, 0, 1, 0]),  # Pat
        (np.random.rand(16, 8, 8), [0, 0, 0, 1]),  # Nothing
    ]

    epochs = 1000
    for epoch in range(epochs):
        total_loss = 0
        for inputs, target in dataset:
            inputs = np.array(inputs)
            target = np.array(target)
            loss = nn.train(inputs, target)
            total_loss += loss
        print(f"Epoch {epoch + 1}, Loss: {total_loss:.4f}")
import logging
import os
import sys

sys.path.append("{}/lib/oboe/automl".format(os.path.realpath(os.path.dirname(__file__))))
from oboe import AutoLearner

from frameworks.shared.callee import call_run, result
from frameworks.shared.utils import Timer

log = logging.getLogger(__name__)


def run(dataset, config):
    log.info(f"\n**** Testing example of oboe [{config.framework_version}] ****\n")
    method = 'Oboe'  # 'Oboe' or 'TensorOboe'
    problem_type = 'classification'

    from oboe import AutoLearner, error  # This may take around 15 seconds at first run.

    import numpy as np
    from sklearn.datasets import load_iris
    from sklearn.model_selection import train_test_split

    data = load_iris()
    x = np.array(data['data'])
    y = np.array(data['target'])
    x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=0.2)

    m = AutoLearner(p_type=problem_type, runtime_limit=30, method=method, verbose=False)
    m.fit(x_train, y_train)
    y_predicted = m.predict(x_test)

    log.info("prediction error (balanced error rate): {}".format(error(y_test, y_predicted, 'classification')))
    log.info("selected models: {}".format(m.get_models()))

    log.info(f"\n**** Oboe [{config.framework_version}] ****\n")

    is_classification = config.type == 'classification'
    if not is_classification:
        # regression currently fails (as of 26.02.2019: still under development state by oboe team)
        raise ValueError('Regression is not yet supported (under development).')

    X_train = dataset.train.X
    y_train = dataset.train.y

    training_params = {k: v for k, v in config.framework_params.items() if not k.startswith('_')}
    n_cores = config.framework_params.get('_n_cores', config.cores)

    log.info('Running oboe with a maximum time of {}s on {} cores.'.format(config.max_runtime_seconds, n_cores))
    log.warning('We completely ignore the advice to optimize towards metric: {}.'.format(config.metric))

    aml = AutoLearner(p_type='classification' if is_classification else 'regression',
                      n_cores=n_cores,
                      runtime_limit=config.max_runtime_seconds,
                      **training_params)

    aml_models = lambda: [aml.ensemble, *aml.ensemble.base_learners] if len(aml.ensemble.base_learners) > 0 else []

    with Timer() as training:
        try:
            aml.fit(X_train, y_train)
        except IndexError as e:
            if len(aml_models()) == 0:  # incorrect handling of some IndexError in oboe if ensemble is empty
                raise ValueError("Oboe could not produce any model in the requested time.")
            raise e

    log.info('Predicting on the test set.')
    X_test = dataset.test.X
    y_test = dataset.test.y
    with Timer() as predict:
        predictions = aml.predict(X_test)
    predictions = predictions.reshape(len(X_test))

    if is_classification:
        probabilities = "predictions"  # encoding is handled by caller in `__init__.py`
    else:
        probabilities = None

    return result(output_file=config.output_predictions_file,
                  predictions=predictions,
                  truth=y_test,
                  probabilities=probabilities,
                  target_is_encoded=is_classification,
                  models_count=len(aml_models()),
                  training_duration=training.duration,
                  predict_duration=predict.duration)


if __name__ == '__main__':
    call_run(run)

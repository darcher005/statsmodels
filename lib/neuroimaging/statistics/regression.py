"""
This module provides various regression analysis techniques to model the
relationship between the dependent and independent variables.
"""

import numpy as N
import numpy.linalg as L
from enthought import traits
from neuroimaging.statistics import Model
import utils
import gc

class LinearModelIterator(traits.HasTraits):

    iterator = traits.Any()
    outputs = traits.List()

    def __init__(self, iterator, outputs=[], **keywords):
        self.iterator = iter(iterator)
        self.outputs = [iter(output) for output in outputs]

    def model(self, **keywords):
        """
        This method should take the iterator at its current state and
        return a LinearModel object.
        """
        return None

    def fit(self, **keywords):
        """
        Go through an iterator, instantiating model and passing data,
        going through outputs.
        """

        for data in self.iterator:
            shape = data.shape[1:]
            data = data.reshape(data.shape[0], N.product(shape))
            model = self.model()

            results = model.fit(data, **keywords)

            for output in self.outputs:
                out = output.extract(results)
                if output.nout > 1:
                    out.shape = (output.nout,) + shape
                else:
                    out.shape = shape
                output.next(data=out)

            del(results); gc.collect()


class RegressionOutput(traits.HasTraits):

    """
    A generic output for regression. Key feature is that it has
    an \'extract\' method which is called on an instance of
    RegressionModelResults.
    """

    Tmax = traits.Float(100.)
    Tmin = traits.Float(-100.)
    Fmax = traits.Float(100.)

    def __init__(self, iterator, **keywords):
        self.iterator = iter(iterator)
        traits.HasTraits.__init__(**keywords)

    def __iter__(self):
        return self

    def extract(self, results):
        return 0.

class RegressionModelResults(traits.HasTraits):
    """
    A container for results from fitting a regression model.
    Key attributes
    RegressionModelResults.
    """

    def __init__(self):
        return

    def t(self, column=None):
        if not hasattr(self, '_sd'):
            self.sd()
        if column is None:
            _t = N.zeros(_beta.shape, N.float64)
            for i in range(self.beta.shape[0]):
                _t[i] = _beta[i] * utils.recipr((self._sd * self.sqrt(self.normalized_cov_beta[i,i])))
        else:
            i = column
            _t = _beta[i] * utils.recipr((self._sd * self.sqrt(self.normalized_cov_beta[i,i])))
        return _t

    def sd(self):
        if not hasattr(self, 'resid'):
            raise ValueError, 'need residuals to estimate standard deviation'
        self._sd = N.sqrt(self.scale)

    def norm_resid(self):
        if not hasattr(self, 'resid'):
            raise ValueError, 'need normalized residuals to estimate standard deviation'
        if not hasattr(self, '_sd'):
            self.sd()
        test = N.greater(_sd, 0)
        sdd = utils.recipr(self._sd) / N.sqrt(self.df)
        norm_resid = self.resid * N.multiply.outer(N.ones(Y.shape[0]), sdd)
        return norm_resid

    def predict(self, design):
        return N.dot(design, self.beta)

    def Rsq(self):
        """
        Return the R^2 value for each row of the response Y.
        """
        self.Ssq = N.std(Y)**2
        Rsq = self.scale / self.Ssq
        return Rsq

    def cov_beta(self, matrix=None, column=None, scale=None, other=None):
        """
        Returns the variance/covariance matrix of a linear contrast
        of the estimates of beta, multiplied by scale which
        will usually be an estimate of sigma^2. The covariance of
        interest is either specified as a (set of) column(s) or a matrix.
        """
        if scale is None:
            scale = self.scale

        if column is not None:
            return self.normalized_cov_beta[column][column] * scale

        elif matrix is not None:
            if other is None:
                other = matrix
            tmp = N.dot(matrix, N.dot(self.normalized_cov_beta, N.transpose(other)))
            return tmp * scale

    def Tcontrast(self, matrix, t=True, sd=True, scale=None):
        """
        Compute a Tcontrast for a row vector matrix. To get the t-statistic
        for a single column, use self.t(column=column).
        """

        if not hasattr(self, '_sd'):
            self.sd()
        results = ContrastResults()

        results.effect = N.dot(matrix, self.beta)
        if sd:
            results.sd = N.sqrt(self.cov_beta(matrix=matrix)) * self._sd
        if t:
            results.t = results.effect * utils.recipr(results.sd)
        return results

    def Fcontrast(self, matrix, eff=True, t=True, sd=True, scale=None, invcov=None):
        """
        Compute an Fcontrast for a contrast matrix. To get the t-statistic
        for a single column, use self.t(column=column).

        Here, matrix M is assumed to be non-singular. More precisely,

        M pX pX' M'

        is assumed invertible. Here, pX is the generalized inverse of the
        design matrix of the model. There can be problems in non-OLS models
        where the rank of the covariance of the noise is not full.

        See the statistics.contrast module to see how to specify contrasts.
        In particular, the matrices from these contrasts will always be
        non-singular in the sense above.

        """

        results = ContrastResults()
        cbeta = N.dot(matrix, self.beta)

        q = matrix.shape[0]
        if invcov is None:
            invcov = L.inv(self.cov_beta(matrix=matrix, scale=1.0))
        results.F = N.add.reduce(N.dot(invcov, cbeta) * cbeta, 0) * utils.recipr((q * self.scale))
        return results

class ContrastResults:
    """
    Results from looking at a particular contrast of coefficients in
    a regression model. The class does nothing, it is a container
    for the results from T and F contrasts.
    """
    pass

class OLSModel(Model):

    """
    A simple ordinary least squares model.
    """

    design = traits.Any()

    def __init__(self, **keywords):
        Model.__init__(self, **keywords)
        try:
            self.setup()
        except:
            pass

    def _design_changed(self):
        self.wdesign = self.design

    def _wdesign_changed(self):
        self.setup()

    def setup(self):
        self.calc_beta = L.pinv(self.wdesign)
        self.normalized_cov_beta = N.dot(self.calc_beta, N.transpose(self.calc_beta))
        self._df_resid = int(N.around(self.wdesign.shape[0] - N.add.reduce(N.diagonal(N.dot(self.calc_beta, self.wdesign)))))

    def initialize(self, design, **keywords):
        self.design = design

    def df_resid(self, **keywords):
        return self._df_resid

    def whiten(self, Y):
        return Y

    def fit(self, Y, **keywords):

        if not hasattr(self, 'calc_beta'):
            self.setup()

        Z = self.whiten(Y)

        lfit = RegressionModelResults()

        lfit.beta = N.dot(self.calc_beta, Z)
        lfit.normalized_cov_beta = self.normalized_cov_beta
        lfit.df_resid = self.df_resid
        lfit.resid = Z - N.dot(self.wdesign, lfit.beta)

        lfit.scale = N.add.reduce(lfit.resid**2) / lfit.df_resid()

        lfit.Z = Z # just in case

        return lfit

class ARModel(OLSModel):
    """
    A regression model with an AR(1) covariance structure.

    Eventually, this will be AR(p) -- all that is needed is to
    determine the self.whiten method from AR(p) parameters.
    """

    rho = traits.Float() # for now just do AR(1) -- not hard to do AR(p)
                         # the only the needs to be done is the whiten method
                         # for this -- we should use the cholesky trick of
                         # a pxp matrix

    def _design_changed(self):
        self.wdesign = self.whiten(self.design)

    def _rho_changed(self):
        self._design_changed()

    def whiten(self, X):
        factor = 1. / N.sqrt(1 - self.rho**2)
        return N.concatenate([[X[0]], (X[1:] - self.rho * X[0:-1]) * factor])


class WLSModel(ARModel):
    """
    A (weighted least square) regression model with diagonal but non-identity
    covariance structure. The weights are proportional to the inverse of the
    variance of the observations.

    """

    weights = traits.Any()

    def _weights_changed(self):
        self._design_changed()

    def whiten(self, X):
        if X.ndim == 1:
            return X / N.sqrt(self.weights)
        elif X.ndim == 2:
            c = N.sqrt(self.weights)
            v = N.zeros(X.shape, N.float64)
            for i in range(X.shape[1]):
                v[:,i] = X[:,i] / c
            return v

def contrastfromcols(T, D, pinv=None, warn=True):
    """
    From an n x p design matrix D and a matrix T, tries
    to determine a p x q contrast matrix C which
    determines a contrast of full rank, i.e. the
    n x q matrix

    dot(transpose(C), pinv(D))

    is full rank.

    T must satisfy either T.shape[0] == n or T.shape[1] == p.

    Note that this always produces a meaningful contrast, not always
    with the intended properties because q is always non-zero unless
    T is identically 0. That is, it produces a contrast that spans
    the column space of T (after projection onto the column space of D).

    """

    n, p = D.shape

    if T.shape[0] != n and T.shape[1] != p:
        raise ValueError, 'shape of T and D mismatched'

    if pinv is None:
        pinv = L.pinv(D)

    if T.shape[0] == n:
        C = N.transpose(N.dot(pinv, T))
    else:
        C = T

    Tp = N.dot(D, N.transpose(C))

    if utils.rank(Tp) != Tp.shape[1]:
        Tp = utils.fullrank(Tp)
        C = N.transpose(N.dot(pinv, Tp))

    return N.squeeze(C)

def isestimable(C, D, pinv=None, warn=True):
    """
    From an q x p contrast matrix C and an n x p design matrix T, tries
    if the contrast C is estimable by looking at the rank of [D,C] and
    verifying it is the same as the rank of D.
    """

    new = N.concatenate([C, D])
    if utils.rank(new) != utils.rank(D):
        return False
    return True
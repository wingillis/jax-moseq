import jax, jax.numpy as jnp, jax.random as jr
import tensorflow_probability.substrates.jax.distributions as tfd
from dynamax.hidden_markov_model.inference import hmm_posterior_sample

from jax_moseq.utils import safe_cho_factor
na = jnp.newaxis

def sample_vonmises(seed, theta, kappa):
    return tfd.VonMises(theta, kappa).sample(seed=seed)

def sample_vonmises_fisher(seed, direction):
    kappa = jnp.sqrt((direction**2).sum(-1))
    direction = direction / kappa[...,na]
    return tfd.VonMisesFisher(direction, kappa).sample(seed=seed)

def sample_gamma(seed, a, b):
    return jr.gamma(seed, a) / b

def sample_inv_gamma(seed, a, b):
    return 1/sample_gamma(seed, a, b)

def sample_scaled_inv_chi2(seed, degs, variance):
    return sample_inv_gamma(seed, degs/2, degs*variance/2)

def sample_chi2(seed, degs):
    return jr.gamma(seed, degs/2)*2

def sample_mn(seed, M, U, V):
    G = jr.normal(seed,M.shape)
    G = jnp.dot(safe_cho_factor(U)[0], G)
    G = jnp.dot(G, safe_cho_factor(V)[0].T)
    return M + G

def sample_invwishart(seed,S,nu):
    n = S.shape[0]
    
    chi2_seed, norm_seed = jr.split(seed)
    x = jnp.diag(jnp.sqrt(sample_chi2(chi2_seed, nu - jnp.arange(n))))
    x = x.at[jnp.triu_indices_from(x,1)].set(jr.normal(norm_seed, (n*(n-1)//2,)))
    R = jnp.linalg.qr(x,'r')
    chol, _ = safe_cho_factor(S)
    
    T = jax.scipy.linalg.solve_triangular(R.T,chol.T,lower=True).T
    return jnp.dot(T,T.T)

def sample_mniw(seed, nu, S, M, K):
    sigma = sample_invwishart(seed, S, nu)
    A = sample_mn(seed, M, sigma, K)
    return A, sigma

def sample_hmm_stateseq(seed, transition_matrix, log_likelihoods, mask):
    """Sample state sequences in a Markov chain.
    
    TODO Pass in initial_distribution (Array[num_states])

    Parameters
        seed (PRNGKey)
        transition_matrix (Array[num_states, num_states])
        log_likelihoods (Array[num_timesteps]): sequence of log likelihoods of
            emissions given hidden state and parameters
        mask (BoolArray[num_timesteps]): sequence indicating whether to use an
            emission (1) or not (0)

    Returns
        log_norm (float): Posterior marginal log likelihood
        states (IntArray[num_timesteps]): sequence of sampled states
    """

    num_states = transition_matrix.shape[0]
    initial_distribution = jnp.ones(num_states)/num_states

    masked_log_likelihoods = log_likelihoods * mask[:,None]
    return hmm_posterior_sample(seed, initial_distribution, transition_matrix, masked_log_likelihoods)
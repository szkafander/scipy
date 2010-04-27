from warnings import warn

from numpy import asarray
from scipy.sparse import isspmatrix_csc, isspmatrix_csr, isspmatrix, \
        SparseEfficiencyWarning, csc_matrix

import _superlu

noScikit = False
try:
    import scikits.umfpack as umfpack
except ImportError:
    import umfpack
    noScikit = True

isUmfpack = hasattr( umfpack, 'UMFPACK_OK' )

useUmfpack = True


__all__ = [ 'use_solver', 'spsolve', 'splu', 'factorized' ]

def use_solver( **kwargs ):
    """
    Valid keyword arguments with defaults (other ignored):
      useUmfpack = True
      assumeSortedIndices = False

    The default sparse solver is umfpack when available. This can be changed by
    passing useUmfpack = False, which then causes the always present SuperLU
    based solver to be used.

    Umfpack requires a CSR/CSC matrix to have sorted column/row indices. If
    sure that the matrix fulfills this, pass assumeSortedIndices=True
    to gain some speed.
    """
    if 'useUmfpack' in kwargs:
        globals()['useUmfpack'] = kwargs['useUmfpack']

    if isUmfpack:
        umfpack.configure( **kwargs )


def spsolve(A, b, permc_spec=2):
    """Solve the sparse linear system Ax=b
    """
    if isspmatrix( b ):
        b = b.toarray()

    if b.ndim > 1:
        if max( b.shape ) == b.size:
            b = b.squeeze()
        else:
            raise ValueError, "rhs must be a vector (has shape %s)" % (b.shape,)

    if not (isspmatrix_csc(A) or isspmatrix_csr(A)):
        A = csc_matrix(A)
        warn('spsolve requires CSC or CSR matrix format', SparseEfficiencyWarning)

    A.sort_indices()
    A = A.asfptype()  #upcast to a floating point format

    M, N = A.shape
    if (M != N):
        raise ValueError, "matrix must be square (has shape %s)" % (M,N)
    if M != b.size:
        raise ValueError, "matrix - rhs size mismatch (%s - %s)"\
              % (A.shape, b.size)


    if isUmfpack and useUmfpack:
        if noScikit:
            warn( 'scipy.sparse.linalg.dsolve.umfpack will be removed,'\
                    ' install scikits.umfpack instead', DeprecationWarning )
        if A.dtype.char not in 'dD':
            raise ValueError, "convert matrix data to double, please, using"\
                  " .astype(), or set linsolve.useUmfpack = False"

        b = asarray(b, dtype=A.dtype).reshape(-1)

        family = {'d' : 'di', 'D' : 'zi'}
        umf = umfpack.UmfpackContext( family[A.dtype.char] )
        return umf.linsolve( umfpack.UMFPACK_A, A, b,
                             autoTranspose = True )

    else:
        if isspmatrix_csc(A):
            flag = 1 # CSC format
        else:
            flag = 0 # CSR format

        b = asarray(b, dtype=A.dtype)
        options = dict(ColPerm=permc_spec)
        return _superlu.gssv(N, A.nnz, A.data, A.indices, A.indptr, b, flag,
                             options=options)[0]

def splu(A, permc_spec=2, diag_pivot_thresh=1.0,
         drop_tol=0.0, relax=1, panel_size=10):
    """
    A linear solver, for a sparse, square matrix A, using LU decomposition where
    L is a lower triangular matrix and U is an upper triagular matrix.

    Returns a factored_lu object. (scipy.sparse.linalg.dsolve._superlu.SciPyLUType)

    See scipy.sparse.linalg.dsolve._superlu.dgstrf for more info.
    """

    if not isspmatrix_csc(A):
        A = csc_matrix(A)
        warn('splu requires CSC matrix format', SparseEfficiencyWarning)

    A.sort_indices()
    A = A.asfptype()  #upcast to a floating point format

    M, N = A.shape
    if (M != N):
        raise ValueError, "can only factor square matrices" #is this true?

    ilu = (drop_tol != 0)
    options = dict(ILU_DropTol=drop_tol, DiagPivotThresh=diag_pivot_thresh,
                   ColPerm=permc_spec)
    return _superlu.gstrf(N, A.nnz, A.data, A.indices, A.indptr,
                          relax=relax, panel_size=panel_size, ilu=ilu,
                          options=options)

def factorized( A ):
    """
    Return a fuction for solving a sparse linear system, with A pre-factorized.

    Example:
      solve = factorized( A ) # Makes LU decomposition.
      x1 = solve( rhs1 ) # Uses the LU factors.
      x2 = solve( rhs2 ) # Uses again the LU factors.
    """
    if isUmfpack and useUmfpack:
        if noScikit:
            warn( 'scipy.sparse.linalg.dsolve.umfpack will be removed,'\
                    ' install scikits.umfpack instead', DeprecationWarning )

        if not isspmatrix_csc(A):
            A = csc_matrix(A)
            warn('splu requires CSC matrix format', SparseEfficiencyWarning)

        A.sort_indices()
        A = A.asfptype()  #upcast to a floating point format

        if A.dtype.char not in 'dD':
            raise ValueError, "convert matrix data to double, please, using"\
                  " .astype(), or set linsolve.useUmfpack = False"

        family = {'d' : 'di', 'D' : 'zi'}
        umf = umfpack.UmfpackContext( family[A.dtype.char] )

        # Make LU decomposition.
        umf.numeric( A )

        def solve( b ):
            return umf.solve( umfpack.UMFPACK_A, A, b, autoTranspose = True )

        return solve
    else:
        return splu( A ).solve

long_python_challenges = [
    {
        "code": (
            "def binary_search(arr, target):\n"
            "    left, right = 0, len(arr) - 1\n"
            "    while left <= right:\n"
            "        mid = (left + right) // 2\n"
            "        if arr[mid] == target:\n"
            "            return mid\n"
            "        elif arr[mid] < target:\n"
            "            left = mid + 1\n"
            "        else:\n"
            "            right = mid - 1\n"
            "    return -1\n\n"
            "data = [10, 22, 35, 47, 59, 63, 78, 91]\n"
            "print(binary_search(data, 63))"
        ),
        "expected": "5\n",
    },
    {
        "code": (
            "class Stack:\n"
            "    def __init__(self):\n"
            "        self.items = []\n"
            "    def push(self, item):\n"
            "        self.items.append(item)\n"
            "    def pop(self):\n"
            "        if not self.is_empty():\n"
            "            return self.items.pop()\n"
            "        raise IndexError('pop from empty stack')\n"
            "    def is_empty(self):\n"
            "        return len(self.items) == 0\n"
            "    def peek(self):\n"
            "        if not self.is_empty():\n"
            "            return self.items[-1]\n"
            "        return None\n\n"
            "s = Stack()\n"
            "s.push(10)\n"
            "s.push(20)\n"
            "s.push(30)\n"
            "print(s.pop(), s.peek())"
        ),
        "expected": "30 20\n",
    },
    {
        "code": (
            "def merge_sort(arr):\n"
            "    if len(arr) <= 1:\n"
            "        return arr\n"
            "    mid = len(arr) // 2\n"
            "    left = merge_sort(arr[:mid])\n"
            "    right = merge_sort(arr[mid:])\n"
            "    return merge(left, right)\n\n"
            "def merge(left, right):\n"
            "    result = []\n"
            "    i = j = 0\n"
            "    while i < len(left) and j < len(right):\n"
            "        if left[i] < right[j]:\n"
            "            result.append(left[i])\n"
            "            i += 1\n"
            "        else:\n"
            "            result.append(right[j])\n"
            "            j += 1\n"
            "    result.extend(left[i:])\n"
            "    result.extend(right[j:])\n"
            "    return result\n\n"
            "print(merge_sort([38, 27, 43, 3, 9, 82, 10]))"
        ),
        "expected": "[3, 9, 10, 27, 38, 43, 82]\n",
    },
    {
        "code": (
            "from collections import deque\n\n"
            "def bfs(graph, start):\n"
            "    visited = []\n"
            "    queue = deque([start])\n"
            "    visited.append(start)\n"
            "    while queue:\n"
            "        node = queue.popleft()\n"
            "        for neighbor in graph[node]:\n"
            "            if neighbor not in visited:\n"
            "                visited.append(neighbor)\n"
            "                queue.append(neighbor)\n"
            "    return visited\n\n"
            "g = {\n"
            "    'A': ['B', 'C'],\n"
            "    'B': ['A', 'D', 'E'],\n"
            "    'C': ['A', 'F'],\n"
            "    'D': ['B'],\n"
            "    'E': ['B', 'F'],\n"
            "    'F': ['C', 'E']\n"
            "}\n"
            "print(bfs(g, 'A'))"
        ),
        "expected": "['A', 'B', 'C', 'D', 'E', 'F']\n",
    },
    {
        "code": (
            "def rotate_matrix(matrix):\n"
            "    n = len(matrix)\n"
            "    for i in range(n):\n"
            "        for j in range(i, n):\n"
            "            matrix[i][j], matrix[j][i] = matrix[j][i],"
            " matrix[i][j]\n"
            "    for i in range(n):\n"
            "        matrix[i].reverse()\n"
            "    return matrix\n\n"
            "mat = [\n"
            "    [1, 2, 3],\n"
            "    [4, 5, 6],\n"
            "    [7, 8, 9]\n"
            "]\n"
            "print(rotate_matrix(mat))"
        ),
        "expected": "[[7, 4, 1], [8, 5, 2], [9, 6, 3]]\n",
    },
    {
        "code": (
            "def fibonacci_memo(n, memo=None):\n"
            "    if memo is None:\n"
            "        memo = {}\n"
            "    if n in memo:\n"
            "        return memo[n]\n"
            "    if n <= 2:\n"
            "        return 1\n"
            "    memo[n] = fibonacci_memo(n - 1, memo) + fibonacci_memo(n - 2,"
            " memo)\n"
            "    return memo[n]\n\n"
            "print([fibonacci_memo(i) for i in range(1, 10)])"
        ),
        "expected": "[1, 1, 2, 3, 5, 8, 13, 21, 34]\n",
    },
    {
        "code": (
            "class InvalidAgeError(Exception):\n"
            "    pass\n\n"
            "def validate_age(age):\n"
            "    if age < 0:\n"
            "        raise InvalidAgeError('Age cannot be negative')\n"
            "    if age > 150:\n"
            "        raise ValueError('Age is unrealistically high')\n"
            "    return f'Age {age} is valid'\n\n"
            "try:\n"
            "    print(validate_age(-5))\n"
            "except (InvalidAgeError, ValueError) as e:\n"
            "    print(f'Caught error: {type(e).__name__} - {e}')"
        ),
        "expected": "Caught error: InvalidAgeError - Age cannot be negative\n",
    },
    {
        "code": (
            "def is_balanced(expression):\n"
            "    stack = []\n"
            "    mapping = {')': '(', '}': '{', ']': '['}\n"
            "    for char in expression:\n"
            "        if char in mapping.values():\n"
            "            stack.append(char)\n"
            "        elif char in mapping.keys():\n"
            "            if not stack or stack.pop() != mapping[char]:\n"
            "                return False\n"
            "    return len(stack) == 0\n\n"
            "print(is_balanced('{[()]}'), is_balanced('{[(])}'))"
        ),
        "expected": "True False\n",
    },
    {
        "code": (
            "def sieve_of_eratosthenes(limit):\n"
            "    if limit < 2:\n"
            "        return []\n"
            "    primes = [True] * (limit + 1)\n"
            "    primes[0] = primes[1] = False\n"
            "    for p in range(2, int(limit**0.5) + 1):\n"
            "        if primes[p]:\n"
            "            for i in range(p * p, limit + 1, p):\n"
            "                primes[i] = False\n"
            "    return [i for i, is_prime in enumerate(primes) if is_prime]\n\n"
            "print(sieve_of_eratosthenes(30))"
        ),
        "expected": "[2, 3, 5, 7, 11, 13, 17, 19, 23, 29]\n",
    },
    {
        "code": (
            "class SimpleCache:\n"
            "    def __init__(self, capacity):\n"
            "        self.capacity = capacity\n"
            "        self.cache = {}\n"
            "    def get(self, key):\n"
            "        if key not in self.cache:\n"
            "            return -1\n"
            "        self.cache[key] = self.cache.pop(key)\n"
            "        return self.cache[key]\n"
            "    def put(self, key, value):\n"
            "        if key in self.cache:\n"
            "            self.cache.pop(key)\n"
            "        elif len(self.cache) >= self.capacity:\n"
            "            oldest_key = next(iter(self.cache))\n"
            "            self.cache.pop(oldest_key)\n"
            "        self.cache[key] = value\n\n"
            "cache = SimpleCache(2)\n"
            "cache.put(1, 1)\n"
            "cache.put(2, 2)\n"
            "print(cache.get(1))\n"
            "cache.put(3, 3)\n"
            "print(cache.get(2))"
        ),
        "expected": "1\n-1\n",
    },
]
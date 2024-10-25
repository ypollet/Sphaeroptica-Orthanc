# Sphaeroptica - 3D Viewer on calibrated

# Copyright (C) 2023 Yann Pollet, Royal Belgian Institute of Natural Sciences

#

# This program is free software: you can redistribute it and/or

# modify it under the terms of the GNU General Public License as

# published by the Free Software Foundation, either version 3 of the

# License, or (at your option) any later version.

# 

# This program is distributed in the hope that it will be useful, but

# WITHOUT ANY WARRANTY; without even the implied warranty of

# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU

# General Public License for more details.

#

# You should have received a copy of the GNU General Public License

# along with this program. If not, see <http://www.gnu.org/licenses/>.


from enum import Enum
import numpy as np

HEIGHT_COMPONENT = 25

class Indexes(Enum):
    HOME = 0
    REC = 1

class Scale(Enum):
    m = 1
    dm = 0.1
    cm = 0.01
    mm = 0.001
    µm = 0.000001
    nm = 0.000000001

class Action(Enum):
    SELECT = 0
    DELETE = 1
    HIDE = 2


class ProjPoint():
    """object containing the projection matrix of the image and the pixel for each landmark posed
    """

    def __init__(self, proj_mat : np.matrix, pixel_point : np.ndarray) -> None:
        self.proj_mat = proj_mat
        self.pixel_point = pixel_point
    
    def __str__(self) -> str:
        return f"{self.proj_mat} x {self.pixel_point}"

class Pose():
    """Landmark posed on image
    """

    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)  
    
    def scaled(self, factor):
        return Pose(round(self.x*factor), round(self.y*factor))
    
    def __str__(self) -> str:
        return (self.x, self.y).__str__()
    
    def to_array(self) -> tuple:
        return [self.x, self.y]
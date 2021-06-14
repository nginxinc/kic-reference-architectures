import pulumi
from ingress_controller_image import IngressControllerImage, IngressControllerImageArgs

stack_name = pulumi.get_stack()
project_name = pulumi.get_project()

# kic_src_url:
# By default the latest version of the NGINX Kubernetes Ingress Controller
# source code will be downloaded and built unless an alternative URL is
# provided for the kic_src_url parameter. This URL can also point to a
# directory on the local file system.
#
# make_target:
# This parameter informs the image creation build script what type of
# Docker image to build. You will need to check the source code to know
# exactly what targets are available. As of 1.11.2, the following make
# targets are available:
#   debian-image (default)
#   alpine-image
#   debian-image-plus
#   debian-image-nap-plus
#   openshift-image
#   openshift-image-plus
#   openshift-image-nap-plus
#   debian-image-opentracing
#   debian-image-opentracing-plus
#
image_args = IngressControllerImageArgs(make_target='debian-image')

# Download KIC source code, run `make`, and build Docker images
ingress_image = IngressControllerImage(name='nginx-ingress-controller',
                                       kic_image_args=image_args)

pulumi.export('ingress_image', ingress_image)

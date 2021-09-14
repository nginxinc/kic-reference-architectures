import pulumi

from ingress_controller_image import IngressControllerImage
from ingress_controller_image_builder_args import IngressControllerImageBuilderArgs
from ingress_controller_image_puller_args import IngressControllerImagePullerArgs
from nginx_plus_args import NginxPlusArgs

stack_name = pulumi.get_stack()
project_name = pulumi.get_project()

config = pulumi.Config('kic')
image_origin = config.get('image_origin')
if not image_origin:
    pulumi.log.info('kic:image_origin not specified, defaulting to: repository')
    image_origin = 'registry'

make_target = config.get('make_target')
kic_src_url = config.get('src_url')
always_rebuild = config.get_bool('always_rebuild')

plus_config = config.get_object('nginx_plus')
if plus_config:
    nginx_plus_args = NginxPlusArgs(key_path=plus_config.get('kic:key_path'),
                                    cert_path=plus_config.get('kic:cert_path'))
else:
    nginx_plus_args = None

# Below is a crucial fork in logic where if 'source' is specified, we build the
# KIC container image from source code. If 'registry' is specified, we pull an
# existing image from a container registry.
#
# In the case of the registry workflow, authentication (login or certs) need to
# be configured before this script is ran.

if image_origin == 'source':
    image_args = IngressControllerImageBuilderArgs(make_target=make_target,
                                                   kic_src_url=kic_src_url,
                                                   always_rebuild=always_rebuild,
                                                   nginx_plus_args=nginx_plus_args)

    # Download KIC source code, run `make`, and build Docker images
    ingress_image = IngressControllerImage(name='nginx-ingress-controller',
                                           kic_image_args=image_args)
elif image_origin == 'registry':
    image_args = IngressControllerImagePullerArgs(image_name=config.get('image_name'))
    ingress_image = IngressControllerImage(name='nginx-ingress-controller',
                                           kic_image_args=image_args)
else:
    raise RuntimeError(f'unknown image_origin: {image_origin}')

pulumi.export('ingress_image', ingress_image)

import pulumi

from ingress_controller_image import IngressControllerImage, IngressControllerImageArgs, NginxPlusArgs

stack_name = pulumi.get_stack()
project_name = pulumi.get_project()

config = pulumi.Config('kic')
make_target = config.get('make_target')
kic_src_url = config.get('src_url')
always_rebuild = config.get_bool('always_rebuild')

plus_config = config.get_object('nginx_plus')
if plus_config:
    nginx_plus_args = NginxPlusArgs(key_path=plus_config.get('kic:key_path'),
                                    cert_path=plus_config.get('kic:cert_path'))
else:
    nginx_plus_args = None

image_args = IngressControllerImageArgs(make_target=make_target,
                                        kic_src_url=kic_src_url,
                                        always_rebuild=always_rebuild,
                                        nginx_plus_args=nginx_plus_args)

# Download KIC source code, run `make`, and build Docker images
ingress_image = IngressControllerImage(name='nginx-ingress-controller',
                                       kic_image_args=image_args)

pulumi.export('ingress_image', ingress_image)

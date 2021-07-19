import os
import unittest
import ingress_controller_image as kic_image


class TestKICImage(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.kic_image_provider = kic_image.IngressControllerImageProvider()

    def assertStrEqual(self, first, second, msg=None):
        self.assertEqual(first=str(first), second=str(second), msg=msg)

    def test_parse_image_name_from_output(self):
        stdout = '    Docker version 20.10.6, build 370c289' + os.linesep + \
                 '    docker build --build-arg IC_VERSION=1.11.1- --build-arg GIT_COMMIT= ' + \
                 '--build-arg VERSION=1.11.1 --tar get container -f build/Dockerfile ' + \
                 '-t 2423423422.dkr.ecr.us-west-9.amazonaws.com/nginx-kic:1.11.1 . --build-arg BUILD_OS=debian'
        expected = kic_image.DockerImageName('2423423422.dkr.ecr.us-west-9.amazonaws.com/nginx-kic', '1.11.1')
        actual = self.kic_image_provider.parse_image_name_from_output(stdout)
        self.assertStrEqual(expected, actual)

    def test_parse_image_name_from_output_with_inconsistent_spacing(self):
        stdout = '    Docker version 20.10.6, build 370c289' + os.linesep + \
                 '    docker    build  --build-arg IC_VERSION=1.11.1-    --build-arg GIT_COMMIT= ' + \
                 '--build-arg   VERSION=1.11.1 --tar get container   -f   build/Dockerfile ' + \
                 '  -t  2423423422.dkr.ecr.us-west-9.amazonaws.com/nginx-kic:1.11.1 . --build-arg BUILD_OS=debian'
        expected = kic_image.DockerImageName('2423423422.dkr.ecr.us-west-9.amazonaws.com/nginx-kic', '1.11.1')
        actual = self.kic_image_provider.parse_image_name_from_output(stdout)
        self.assertStrEqual(expected, actual)

    def test_parse_image_name_from_output_with_continuations(self):
        stdout = '    Docker version 20.10.6, build 370c289' + os.linesep + \
                 '    docker build --build-arg IC_VERSION=1.11.1- --build-arg GIT_COMMIT= ' + '\\' + os.linesep + \
                 '--build-arg VERSION=1.11.1 --tar get container -f build/Dockerfile ' + '\\' + os.linesep + \
                 '-t 2423423422.dkr.ecr.us-west-9.amazonaws.com/nginx-kic:1.11.1 . --build-arg BUILD_OS=debian'
        expected = kic_image.DockerImageName('2423423422.dkr.ecr.us-west-9.amazonaws.com/nginx-kic', '1.11.1')
        actual = self.kic_image_provider.parse_image_name_from_output(stdout)
        self.assertStrEqual(expected, actual)

    def test_parse_image_name_from_output_with_tag(self):
        stdout = '    Docker version 20.10.6, build 370c289' + os.linesep + \
                 '    docker build --build-arg IC_VERSION=1.11.1- --build-arg GIT_COMMIT= ' + \
                 '--build-arg VERSION=1.11.1 --tar get container -f build/Dockerfile ' + \
                 '--tag 2423423422.dkr.ecr.us-west-9.amazonaws.com/nginx-kic:1.11.1 . --build-arg BUILD_OS=debian'
        expected = kic_image.DockerImageName('2423423422.dkr.ecr.us-west-9.amazonaws.com/nginx-kic', '1.11.1')
        actual = self.kic_image_provider.parse_image_name_from_output(stdout)
        self.assertStrEqual(expected, actual)

    def test_parse_image_name_from_output_with_multiple_slashes(self):
        stdout = '    Docker version 20.10.6, build 370c289' + os.linesep + \
                 '    docker build --build-arg IC_VERSION=1.11.1- --build-arg GIT_COMMIT= ' + \
                 '--build-arg VERSION=1.11.1 --tar get container -f build/Dockerfile ' + \
                 '-t myregistryhost:5000/fedora/nginx-kic:1.11.1 . --build-arg BUILD_OS=debian'
        expected = kic_image.DockerImageName('myregistryhost:5000/fedora/nginx-kic', '1.11.1')
        actual = self.kic_image_provider.parse_image_name_from_output(stdout)
        self.assertStrEqual(expected, actual)

    def test_parse_image_name_from_output_with_single_quotes(self):
        stdout = '    Docker version 20.10.6, build 370c289' + os.linesep + \
                 '    docker build --build-arg IC_VERSION=1.11.1- --build-arg GIT_COMMIT= ' + \
                 '--build-arg VERSION=1.11.1 --tar get container -f build/Dockerfile ' + \
                 "-t 'myregistryhost:5000/fedora/nginx-kic:1.11.1' . --build-arg BUILD_OS=debian"
        expected = kic_image.DockerImageName('myregistryhost:5000/fedora/nginx-kic', '1.11.1')
        actual = self.kic_image_provider.parse_image_name_from_output(stdout)
        self.assertStrEqual(expected, actual)

    def test_parse_image_name_from_output_with_double_quotes(self):
        stdout = '    Docker version 20.10.6, build 370c289' + os.linesep + \
                 '    docker build --build-arg IC_VERSION=1.11.1- --build-arg GIT_COMMIT= ' + \
                 '--build-arg VERSION=1.11.1 --tar get container -f build/Dockerfile ' + \
                 '-t "myregistryhost:5000/fedora/nginx-kic:1.11.1" . --build-arg BUILD_OS=debian'
        expected = kic_image.DockerImageName('myregistryhost:5000/fedora/nginx-kic', '1.11.1')
        actual = self.kic_image_provider.parse_image_name_from_output(stdout)
        self.assertStrEqual(expected, actual)

    def test_parse_image_name_from_output_without_tag(self):
        stdout = '    Docker version 20.10.6, build 370c289' + os.linesep + \
                 '    docker build --build-arg IC_VERSION=1.11.1- --build-arg GIT_COMMIT= ' + \
                 '--build-arg VERSION=1.11.1 --tar get container -f build/Dockerfile ' + \
                 '. --build-arg BUILD_OS=debian'
        expected = None
        actual = self.kic_image_provider.parse_image_name_from_output(stdout)
        self.assertEqual(expected, actual)

    def test_parse_image_id_from_output_matching_line(self):
        stderr = '    #19 writing image sha256:9358beb5cb1c6d6a9c005b18bdad08b0f2259b82d32687b03334256cbd500997 0.0s done'
        expected = 'sha256:9358beb5cb1c6d6a9c005b18bdad08b0f2259b82d32687b03334256cbd500997'
        actual = self.kic_image_provider.parse_image_id_from_output(stderr)
        self.assertEqual(expected, actual)

    def test_parse_image_id_from_output_non_matching_line(self):
        stderr = '    #19 sha256:e8c613e07b0b7ff33893b694f7759a10d42e180f2b4dc349fb57dc6b71dcab00'
        actual = self.kic_image_provider.parse_image_id_from_output(stderr)
        self.assertEqual(None, actual)

    def test_parse_image_id_from_output_matching_line_in_multiple_lines(self):
        stderr = '''    fatal: not a git repository (or any of the parent directories): .git
    fatal: not a git repository (or any of the parent directories): .git
    #1 [internal] load build definition from Dockerfile
    #1 sha256:14b46a9847c33680288f606efc1d8af09f2f149e034235645d17e9bc0e5217db
    #1 transferring dockerfile: 38B done
    #1 DONE 0.1s

    #2 [internal] load .dockerignore
    #2 sha256:22dd5e1d145e8237f101b6bbfb9750fa487569c9c39c00652b2f3fe64e74225a
    #2 transferring context: 34B done
    #2 DONE 0.1s

    #3 resolve image config for docker.io/docker/dockerfile:1.0-experimental
    #3 sha256:74c2b22e535000215e4c6e91e97eaf031c745b5077d1b004e21d261b62c88704
    #3 DONE 0.9s

    #4 docker-image://docker.io/docker/dockerfile:1.0-experimental@sha256:cbd6491240cc8894d25e366ba83da19df1187f975dc3a5c2f88ce888ca696174
    #4 sha256:0af8e2916ef66f474d25fbdacb8b917690b037530afe0cb2062890ef568528e9
    #4 CACHED

    #6 [internal] load .dockerignore
    #6 sha256:ddb98238ec7f27bdd81c8ae1075b50b1a4217ab687d7187b76cc12b22cf6a5c4
    #6 DONE 0.0s

    #5 [internal] load build definition from Dockerfile
    #5 sha256:10a831d101b412b1a924c02e2f9d9647a0991ed634b422b8a4fa857ac209716f
    #5 transferring dockerfile: 38B done
    #5 DONE 0.0s

    #8 [internal] load metadata for docker.io/library/nginx:1.19.9
    #8 sha256:626a54e9907761c093d161f20d7cd32606114ead94544f2420cc52ef7c1628eb
    #8 DONE 0.5s

    #7 [internal] load metadata for docker.io/library/golang:1.16-alpine
    #7 sha256:8b63da5e018f0854e06e7ef30abb4b1f70e2a4498e97a24af82c7d09918a0160
    #7 DONE 0.6s

    #10 [debian 1/2] FROM docker.io/library/nginx:1.19.9@sha256:6b5f5eec0ac03442f3b186d552ce895dce2a54be6cb834358040404a242fd476
    #10 sha256:84a8f25c77dd3348c45686634a7a0f34745d0eb1b2f049abb644328876be6eb7
    #10 DONE 0.0s

    #15 [builder 1/3] FROM docker.io/library/golang:1.16-alpine@sha256:49c07aa83790aca732250c2258b5912659df31b6bfa2ab428661bc66833769e1
    #15 sha256:55220455ac16cbe1c42e1fdf5f6ddd793c2e18703a714d55b77fc5af0057b784
    #15 DONE 0.0s

    #9 [internal] helper image for file operations
    #9 sha256:e4c43493b1bb2320466c52248e886014710025b273f224bb96a23b8fb7a1d193
    #9 DONE 0.0s

    #13 [internal] load build context
    #13 sha256:2d0845f04b8e8020f24d87c2bff5391a1f5ee37c525fc37363fe036f4c066804
    #13 transferring context: 346.81kB 0.3s done
    #13 DONE 0.3s

    #12 [files 1/2] RUN mkdir -p /var/lib/nginx /etc/nginx/secrets /etc/nginx/stream-conf.d     && setcap 'cap_net_bind_service=+ep' /usr/sbin/nginx 'cap_net_bind_service=+ep' /usr/sbin/nginx-debug      && chown -R nginx:0 /etc/nginx /var/cache/nginx /var/lib/nginx     && rm -f /etc/nginx/conf.d/* /etc/apt/apt.conf.d/90nginx /etc/apt/sources.list.d/nginx-plus.list
    #12 sha256:871d41b04e24672fb7d934288083a4306a130e0db98c3207f78c3ce71d700200
    #12 CACHED

    #14 [files 2/2] COPY internal/configs/version1/nginx.ingress.tmpl   internal/configs/version1/nginx.tmpl       internal/configs/version2/nginx.virtualserver.tmpl      internal/configs/version2/nginx.transportserver.tmpl /
    #14 sha256:f7e805d6e61f2589e1f5f7664ca7bec42d755a8aa7158e247c6e9300d4e96f1c
    #14 CACHED

    #16 [builder 2/3] COPY . /go/src/github.com/nginxinc/kubernetes-ingress/nginx-ingress/
    #16 sha256:5b42a1e9401eaafd120f4afdf24302a5546551ebe536aba2203c01153e50c720
    #16 CACHED

    #17 [builder 3/3] RUN CGO_ENABLED=0 GOFLAGS='-mod=vendor'   go build -installsuffix cgo -ldflags "-w -X main.version=1.11.1 -X main.gitCommit=" -o /nginx-ingress
    #17 sha256:ee4cb0169858a4fb1e348610c882039425d00f3eb789d480b5252b229ade1252
    #17 CACHED

    #11 [debian 2/2] RUN apt-get update         && apt-get install --no-install-recommends --no-install-suggests -y libcap2-bin    && rm -rf /var/lib/apt/lists/*
    #11 sha256:066c4eb19b5cb6ce34e4100314f61a6f68b02516849c3a22032ca0cfb415d393
    #11 CACHED

    #18 [container 1/1] COPY --chown=nginx:0 --from=builder /nginx-ingress /
    #18 sha256:bea5b420a002950115652fe45386f09a4c0271bb8804cd6dbd55644b3de8eb57
    #18 CACHED

    #19 exporting to image
    #19 sha256:e8c613e07b0b7ff33893b694f7759a10d42e180f2b4dc349fb57dc6b71dcab00
    #19 exporting layers done
    #19 writing image sha256:9358beb5cb1c6d6a9c005b18bdad08b0f2259b82d32687b03334256cbd500997 0.0s done
    #19 naming to 369313531325.dkr.ecr.us-west-2.amazonaws.com/nginx-kic:1.11.1 done
    #19 DONE 0.2s'''
        expected = 'sha256:9358beb5cb1c6d6a9c005b18bdad08b0f2259b82d32687b03334256cbd500997'
        actual = self.kic_image_provider.parse_image_id_from_output(stderr)
        self.assertEqual(expected, actual)
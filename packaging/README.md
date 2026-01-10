## Packaging
This directory contains any supporting files to grant usage of Apprise in various distributions.

Let me know if you'd like to help me host on more platforms or can offer to do it yourself!

### RPM Based Packages
* [EPEL](https://fedoraproject.org/wiki/EPEL) based distributions are only supported if they are of v9 or higher. This includes:
   * Red Hat 10.x (or higher)
   * Scientific OS 10.x (or higher)
   * Oracle Linux 10.x (or higher)
   * Rocky Linux 10.x (or higher)
   * Alma Linux 110.x (or higher)
   * Fedora 29 (or higher)

Provided you are connected to the [EPEL repositories](https://fedoraproject.org/wiki/EPEL), the following will just work for you:
```bash
# python3-apprise: contains all you need to develop with apprise
# apprise: provides the 'apprise' administrative tool
dnf install python3-apprise apprise
```

You can build your own rpm packges with the following:
* EPEL10 (Rocky/RedHat/Oracle Linux)
   ```bash
   tox -e build-el10-rpm
   ```

* EPEL9 (Rocky/RedHat/Oracle Linux)
   ```bash
   tox -e build-el9-rpm
   ```

* Fedora 42
   ```bash
   tox -e build-f42-rpm
   ```

* Fedora Rawhide
   ```bash
   tox -e build-rawhide-rpm
   ```

## Man Pages Information
The man page were generated using [Ronn](http://github.com/rtomayko/ronn/tree/0.7.3).
 - Content is directly written to entries in the **man/\*.md** files _following the
   [the format structure available on the Ronn site](https://github.com/rtomayko/ronn/blob/master/man/ronn.1.ronn)_.
 - Then the following is executed `ronn --roff man/apprise.md` to produce the man/apprise.1 which is used by distributions.

The easiest way to generate the new man page (after updating the `.md` file is:
```bash
# rebuild man page
tox -e man
```
